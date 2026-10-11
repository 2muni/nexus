# GitHub App authentication

Production GitHub provider calls use a fresh installation token for each existing
`gh api` or `gh pr view` invocation. Python 3.9+ standard library, installed OpenSSL
and installed `gh` are required. No personal `gh` login or inherited personal token
is a fallback. No token service, permanent cache, daemon or global credential change
is introduced. Write-plan digests, human approval, source-head checks and provider
interfaces are unchanged; authentication does not authorize publication.

Copy `local/github-app.json.example` to ignored `.runtime/github-app.json` after
creating `.runtime/`. Fill the null values locally: positive App ID, absolute
external private-key file path, exact canonical repository name and numeric ID,
and that repository's installation ID. The example deliberately contains no
deployment identifiers or key path and is invalid until configured. To use another
local JSON file, set `NEXUS_GITHUB_APP_CONFIG` to its path; keep that file outside
tracked material. JSON is data, never sourced or executed. Unknown top-level or
binding keys and duplicate JSON keys fail. This configuration is separate from
the existing Project mapping in `local/github.json` / `NEXUS_GITHUB_CONFIG`.

The private key must reside outside the checkout, be RSA with at least 2048 bits,
owned by the invoking user, mode 0400 or 0600, and a regular file with one hard
link. Symlinks in any component are refused. Parent directories must belong to
the user or root and disallow group/other writes (sticky temporary directories
are allowed). Use the physical absolute path on hosts whose temporary-directory
aliases are symlinks. The verified descriptor stays open through signing to avoid
path replacement between validation and use. Keys with passphrases are unsupported;
there is no interactive prompt. POSIX ownership/mode checks do not audit additional
host ACL policy; the operator must provision the external key appropriately.

Each repository binding's `permissions` is a local ceiling within existing App
installation grants, not a request to change the registration. The helper requests
only the following permissions for the actual command, always with metadata/read:

| Existing command | Additional requested permissions |
| --- | --- |
| Issue/comment REST reads | issues/read |
| Issue/comment approved REST writes | issues/write |
| PR REST reads and `gh pr view` review/check rollup | pull_requests/read |
| Approved PR creation | pull_requests/write |
| Exact source Git ref read | contents/read |
| Project GraphQL reads | issues/read, organization_projects/read |
| Approved Project GraphQL mutation | issues/read, organization_projects/write |

Configure only applicable ceilings; missing permissions fail before a provider
command. User-owned Projects that an installation cannot access remain unavailable;
no personal-token fallback is attempted. Organization Project permission applies
to organization resources: narrowing repository IDs does not isolate the entire
organization Project. Existing exact Project mappings, identity checks and reviewed
write plans retain that responsibility. The PR observation uses the existing
GraphQL rollup, rather than the REST checks/statuses APIs; it adds no new grants.
Unavailable rollup fields/access fail closed and require read validation in the
actual deployment. Fork source refs require a separate exact repository binding
and installation for their owner; no token spans the source and target repositories.

The helper verifies the authenticated App, installation ID/App/owner/type and
suspension, exact repository installation, and current permission grants. It
requests one numeric repository ID and the command's exact permissions. Returned
permissions and expiry (UTC, more than 30 seconds remaining, at most one hour plus
clock tolerance) must match. The token-authenticated repository inventory must
contain exactly the configured ID and canonical name. One repository fits one page;
additional pages, incomplete inventories, aliases and overbroad access are refused.
Existing provider REST/GraphQL pagination flags are passed through unchanged.
Variable-length and stateless installation-token formats are supported.

JWTs and tokens stay in memory. OpenSSL receives the verified key via an inherited
file descriptor and signs stdin into stdout; neither secrets nor the key path enter
command arguments. Authentication uses fixed-origin TLS without redirects or
environment proxies. The `gh` child receives only its token in a scoped environment,
minimal host variables and an empty temporary configuration directory. Personal
tokens, debug/tracing, proxies, custom CA/loader/config inputs and user `gh` configuration
are not inherited. No key/JWT/token is written to disk. Child stderr is suppressed,
failed stdout is withheld, credential-bearing stdout is rejected, and errors use
fixed diagnostics without response bodies or exception traces.

Issued tokens are revoked in `finally`, including validation and command failures.
Failed commands retain their exit status; successful commands become failures if
revocation is unknown. Timeout, process interruption, host failure or a lost token
issuance response can prevent confirmed revocation; expiry bounds remaining access.
No authentication or provider command is replayed. After an ambiguous write or
revocation failure, preserve the reviewed plan and reconcile externally before
retrying; publication may already have happened.

Offline tests explicitly set `NEXUS_GITHUB_OFFLINE_FIXTURE` to an executable absolute
fixture path. This deliberately bypasses App authentication and executes only the
existing command shape, with minimal environment plus `MOCK_*` fixture data; its
results are unauthenticated test evidence. Do not set it in production. The former
`NEXUS_GH_COMMAND` override is refused in production. Authentication tests instead
import the helper, mock its fixed HTTP transport, and generate temporary test-only
keys; they never read deployment credentials or contact GitHub. Run `bash tests/run.sh`.

Sources: installed `gh help environment`, `gh api --help`, `gh pr view --help`, and
GitHub's [JWT requirements](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app),
[App and installation-token API](https://docs.github.com/en/rest/apps/apps), and
[installation inventory/revocation API](https://docs.github.com/en/rest/apps/installations).
