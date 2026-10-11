"""One App token for one existing adapter call; no credentials on stdout or disk."""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
FIELDS = "url,headRefOid,reviewDecision,statusCheckRollup,mergedAt,isDraft"
REPOSITORY = r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*"
PERMISSIONS = {"metadata", "issues", "pull_requests", "contents", "organization_projects"}


class AuthError(Exception):
    """Only fixed, nonsecret diagnostic text crosses this boundary."""


def require(condition, message):
    if not condition:
        raise AuthError(message)


def positive(value):
    return type(value) is int and value > 0


def command_permissions(repository, args):
    """Accept only the two command shapes used by the adapter, never arbitrary gh."""
    require(re.fullmatch(REPOSITORY, repository), "Exact repository required.")
    needed = {"metadata": "read"}
    if args[:2] == ["pr", "view"]:
        require(len(args) == 7 and re.fullmatch(r"[1-9][0-9]*", args[2]) and
                args[3:] == ["--repo", repository, "--json", FIELDS],
                "Unsupported PR observation command.")
        # Existing GraphQL PR rollup reads use pull_requests, not the REST
        # checks/statuses endpoints. Unavailable fields still fail at transport.
        needed["pull_requests"] = "read"
        return needed
    require(args[:3] == ["api", "--hostname", "github.com"] and len(args) >= 4,
            "Unsupported provider command.")
    endpoint = args[3]
    method, query, flags = "GET", None, {}
    index = 4
    while index < len(args):
        flag = args[index]
        require(flag not in flags or flag in {"-f", "-F"}, "Duplicate provider flag.")
        require(flag in {"--method", "--input", "--paginate", "--slurp", "-f", "-F"},
                "Unsupported provider flag.")
        flags[flag] = True
        if flag in {"--paginate", "--slurp"}:
            index += 1
            continue
        require(index + 1 < len(args), "Missing provider flag value.")
        value = args[index + 1]
        if flag == "--method":
            method = value
        if flag in {"-f", "-F"}:
            key, separator, field = value.partition("=")
            require(endpoint == "graphql" and separator and key in
                    {"query", "owner", "number", "id", "project", "content", "item", "field", "option"}
                    and not field.startswith("@"), "Unsupported GraphQL field.")
            if key == "query":
                require(query is None, "Duplicate GraphQL query.")
                query = field
        index += 2
    require(method in {"GET", "POST", "PATCH"}, "Unsupported provider method.")
    require("--slurp" not in flags or "--paginate" in flags, "Slurp requires pagination.")
    if endpoint == "graphql":
        require(query is not None and (query.startswith("query(") or query.startswith("mutation("))
                and "--input" not in flags and "--method" not in flags,
                "Unsupported Project query.")
        needed.update(issues="read", organization_projects=
                      "write" if query.startswith("mutation(") else "read")
    else:
        require(not ({"-f", "-F"} & flags.keys()), "REST fields unsupported.")
        suffix = endpoint.removeprefix("repos/" + repository + "/")
        require(endpoint.startswith("repos/" + repository + "/") and
                re.fullmatch(r"(?:issues|pulls)(?:/[1-9][0-9]*(?:/comments)?)?(?:\?(?:state=all&)?per_page=100)?|git/ref/heads/[A-Za-z0-9_%.\-/]+", suffix),
                "Unsupported repository endpoint.")
        if suffix.startswith("git/"):
            require(method == "GET", "Source ref is read-only.")
            needed["contents"] = "read"
        else:
            needed["issues" if suffix.startswith("issues") else "pull_requests"] = (
                "read" if method == "GET" else "write")
        require((method == "GET" and "--input" not in flags) or
                (method != "GET" and "--input" in flags and "--paginate" not in flags
                 and "?" not in endpoint), "Unsupported REST request shape.")
    return needed


def load_config(path, repository, needed):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate configuration key.")
            result[key] = value
        return result
    with open(path, encoding="utf-8") as stream:
        config = json.load(stream, object_pairs_hook=unique)
    require(type(config) is dict and set(config) ==
            {"version", "app_id", "private_key_path", "repositories"} and
            type(config["version"]) is int and config["version"] == 1 and
            positive(config["app_id"]) and type(config["private_key_path"]) is str and
            type(config["repositories"]) is dict, "Invalid App configuration.")
    binding = config["repositories"].get(repository)
    require(type(binding) is dict and set(binding) == {"id", "installation_id", "permissions"}
            and positive(binding["id"]) and positive(binding["installation_id"]),
            "Repository App binding missing or invalid.")
    permissions = binding["permissions"]
    require(type(permissions) is dict and permissions and
            all(k in PERMISSIONS and v in {"read", "write"} for k, v in permissions.items()),
            "Invalid permission ceiling.")
    require(all(permissions.get(k) in {v, "write"} for k, v in needed.items()),
            "Operation exceeds configured permissions.")
    return config, binding


def key_descriptor(path):
    """Walk without following symlinks; keep the verified file open for signing."""
    key = Path(path)
    require(key.is_absolute() and ".." not in key.parts and not key.is_relative_to(ROOT),
            "Private key must be an external absolute file.")
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in key.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
            info = os.fstat(directory)
            require(info.st_uid in {0, os.getuid()} and
                    (not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX),
                    "Unsafe private key directory.")
        descriptor = os.open(key.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(descriptor)
        if not (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                info.st_mode & 0o777 in {0o400, 0o600} and info.st_nlink == 1):
            os.close(descriptor)
            raise AuthError("Private key requires owned, single-link regular file mode 0400 or 0600.")
        return descriptor
    finally:
        os.close(directory)


def child_environment():
    # No inherited tokens, gh/git debug, config, proxies, custom CA or loader inputs.
    return {key: value for key, value in os.environ.items()
            if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT"}}


def jwt(config):
    executable = shutil.which("openssl")
    require(executable, "OpenSSL unavailable.")
    descriptor = key_descriptor(config["private_key_path"])
    def openssl(arguments, data=None):
        os.lseek(descriptor, 0, os.SEEK_SET)
        result = subprocess.run([executable, *arguments], input=data, capture_output=True,
                                pass_fds=(descriptor,), env=child_environment(), timeout=15)
        require(result.returncode == 0, "App signing failed.")
        return result.stdout
    try:
        # RSA-only public projection; no private key dump or passphrase prompt.
        public = openssl(["rsa", "-in", f"/dev/fd/{descriptor}", "-passin", "pass:", "-pubout"])
        description = openssl(["pkey", "-pubin", "-text", "-noout"], public)
        bits = re.search(rb"Public-Key: \((\d+) bit\)", description)
        require(bits is not None and int(bits[1]) >= 2048, "RSA key must be at least 2048 bits.")
        def encode(data):
            return base64.urlsafe_b64encode(data).rstrip(b"=")
        now = int(time.time())
        signing = encode(b'{"alg":"RS256","typ":"JWT"}') + b"." + encode(
            json.dumps({"iat": now - 60, "exp": now + 540, "iss": str(config["app_id"])},
                       separators=(",", ":")).encode())
        signature = openssl(["dgst", "-sha256", "-sign", f"/dev/fd/{descriptor}",
                             "-passin", "pass:"], signing)
        return (signing + b"." + encode(signature)).decode("ascii")
    finally:
        os.close(descriptor)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise AuthError("Authentication redirect refused.")


def request(method, path, credential, body=None):
    """Fixed TLS origin, no environment proxy, retries, raw errors or response dumps."""
    # Do not let inherited TLS debug/custom-trust inputs affect authentication.
    # Construct directly (create_default_context enables SSLKEYLOGFILE).
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    paths = ssl.get_default_verify_paths()
    cafile = paths.openssl_cafile if os.path.isfile(paths.openssl_cafile) else None
    capath = paths.openssl_capath if os.path.isdir(paths.openssl_capath) else None
    require(cafile or capath, "System TLS trust unavailable.")
    context.load_verify_locations(cafile=cafile, capath=capath)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=context))
    req = urllib.request.Request("https://api.github.com" + path, method=method,
        data=None if body is None else json.dumps(body).encode(), headers={
            "Authorization": "Bearer " + credential, "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "User-Agent": "nexus-github-app",
            "X-GitHub-Api-Version": "2026-03-10"})
    with opener.open(req, timeout=30) as response:
        require(response.status == {"GET": 200, "POST": 201, "DELETE": 204}[method],
                "Authentication response status invalid.")
        data = response.read(2 * 1024 * 1024 + 1)
        require(len(data) <= 2 * 1024 * 1024, "Authentication response too large.")
        return (None if method == "DELETE" else json.loads(data)), response.headers.get("Link", "")


def installation_identity(record, config, binding, repository):
    require(type(record) is dict and positive(record.get("id")) and positive(record.get("app_id")) and
            record.get("id") == binding["installation_id"] and
            record.get("app_id") == config["app_id"] and record.get("suspended_at", True) is None and
            record.get("account", {}).get("login") == repository.split("/")[0] and
            record.get("target_type") in {"User", "Organization"},
            "App installation identity mismatch or suspended.")


def run(repository, args):
    needed = command_permissions(repository, args)
    fixture = os.environ.get("NEXUS_GITHUB_OFFLINE_FIXTURE")
    if fixture is not None:
        require(Path(fixture).is_absolute() and os.access(fixture, os.X_OK),
                "Offline fixture must be an explicit executable absolute path.")
        env = child_environment()
        env.update({k: v for k, v in os.environ.items() if k.startswith("MOCK_")})
        result = subprocess.run([fixture, *args], env=env, capture_output=True, timeout=120)
        return result.returncode, result.stdout if result.returncode == 0 else b""
    require("NEXUS_GH_COMMAND" not in os.environ,
            "Legacy command override refused; use explicit offline fixture for tests.")
    config, binding = load_config(os.environ.get("NEXUS_GITHUB_APP_CONFIG",
                                  str(ROOT / ".runtime/github-app.json")), repository, needed)
    executable = shutil.which("gh")
    require(executable, "GitHub CLI unavailable.")
    app_jwt = jwt(config)
    app, _ = request("GET", "/app", app_jwt)
    require(type(app) is dict and positive(app.get("id")) and app.get("id") == config["app_id"], "App identity mismatch.")
    installation, _ = request("GET", f'/app/installations/{binding["installation_id"]}', app_jwt)
    installation_identity(installation, config, binding, repository)
    require(all(installation.get("permissions", {}).get(k) in {v, "write"}
                for k, v in needed.items()), "Installation lacks required permissions.")
    installed, _ = request("GET", f"/repos/{repository}/installation", app_jwt)
    installation_identity(installed, config, binding, repository)
    token = None
    result = None
    try:
        issued, _ = request("POST", f'/app/installations/{binding["installation_id"]}/access_tokens',
                            app_jwt, {"repository_ids": [binding["id"]], "permissions": needed})
        require(type(issued) is dict and type(issued.get("token")) is str and
                re.fullmatch(r"ghs_[A-Za-z0-9_.-]{16,16380}", issued["token"]), "Malformed installation token.")
        token = issued["token"]  # Also revoke if subsequent validation fails.
        require(issued.get("permissions") == needed, "Token permissions differ from exact request.")
        require(type(issued.get("expires_at")) is str and
                re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", issued["expires_at"]),
                "Invalid token expiry.")
        expiry = datetime.strptime(issued["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        require(30 < expiry - time.time() <= 3660, "Token expired or expiry outside installation lifetime.")
        # Exactly one repository implies one complete page. Reject Link pagination
        # rather than ever treating an incomplete or broader inventory as scoped.
        inventory, link = request("GET", "/installation/repositories?per_page=100", token)
        require(type(inventory) is dict and positive(inventory.get("total_count")) and inventory.get("total_count") == 1 and
                type(inventory.get("repositories")) is list and len(inventory["repositories"]) == 1 and
                not link, "Token repository inventory incomplete or overbroad.")
        record = inventory["repositories"][0]
        require(type(record) is dict and positive(record.get("id")) and record.get("id") == binding["id"] and record.get("full_name") == repository,
                "Token repository identity mismatch.")
        with tempfile.TemporaryDirectory(prefix="nexus-gh-config-") as config_dir:
            env = child_environment()
            env.update(GH_TOKEN=token, GH_HOST="github.com", GH_CONFIG_DIR=config_dir,
                       HOME=config_dir, GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1",
                       GH_NO_EXTENSION_UPDATE_NOTIFIER="1", GH_TELEMETRY="false")
            result = subprocess.run([executable, *args], env=env, capture_output=True, timeout=120)
        if result.returncode == 0:
            require(token.encode() not in result.stdout and app_jwt.encode() not in result.stdout and
                    b"PRIVATE KEY-----" not in result.stdout, "Credential-bearing provider output refused.")
    finally:
        if token is not None:
            try:
                request("DELETE", "/installation/token", token)
            except Exception:
                # A write may already have happened. Keep its original failure code,
                # but never report success when token retirement is unknown.
                if result is None or result.returncode == 0:
                    raise AuthError("Token revocation failed; preserve plan and reconcile, do not replay.") from None
    return result.returncode, result.stdout if result.returncode == 0 else b""


def main():
    try:
        require(len(sys.argv) >= 3, "Repository and provider command required.")
        code, output = run(sys.argv[1], sys.argv[2:])
        if code:
            print("GitHub command failed; preserve plan and reconcile before any retry.", file=sys.stderr)
        else:
            sys.stdout.buffer.write(output)
        return code if code >= 0 else 128 - code
    except AuthError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        print("GitHub App authentication/transport failed; no credential fallback or replay.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
