"""Factual collector conformance through real read ports and an offline gh boundary."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_projects import MOCK as PROJECT_MOCK

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_READS = '''
mode=os.environ.get("MOCK_OBS_MODE", "")
endpoint=next((x for x in args if x.startswith("repos/")), "")
if mode == "unavailable": sys.exit(1)
if endpoint or args[:2] == ["pr", "view"]:
 if mode == "truncated": print('{"broken":');sys.exit()
 if mode == "error": print(json.dumps({"errors":[{"message":"failure"}]}));sys.exit()
 issue={"html_url":"https://github.com/a/b/issues/1","number":1,"node_id":"issue1", "title":"Task", "body":"private requirements", "state":"open", "updated_at":"2026-10-08T00:00:00Z"}
 pr=dict(issue,html_url="https://github.com/a/b/pull/3",number=3,head={"sha":"a"*40,"ref":"feature"},base={"ref":"main"})
 if mode == "wrong_issue": issue["html_url"]="https://github.com/other/b/issues/1"
 if mode == "issue_is_pr": issue["pull_request"]={}
 if mode == "missing_timestamp": issue.pop("updated_at")
 if args[:2] == ["pr", "view"]:
  print(json.dumps(dict(url=pr["html_url"],headRefOid=("b" if mode == "stale_head" else "a")*40,reviewDecision="APPROVED",statusCheckRollup=[dict(name="test",status="COMPLETED",conclusion="SUCCESS")],mergedAt=None,isDraft=False)));sys.exit()
 if "/comments?" in endpoint:
  comments=[dict(id=n,issue_url="https://api.github.com/repos/a/b/issues/1",html_url=f"https://github.com/a/b/issues/1#issuecomment-{n}",body='{"approved":true}',user={"login":"person"},author_association="OWNER",updated_at="2026-10-08T00:00:00Z") for n in [1,2]]
  if mode == "wrong_comment": comments[0]["issue_url"]="https://api.github.com/repos/a/b/issues/2"
  print(json.dumps([[comments[0]],[comments[1]]]));sys.exit()
 if "?state=" in endpoint:
  if mode == "empty_pages": print("[]");sys.exit()
  records=[pr] if "/pulls?" in endpoint else [issue]
  if mode == "wrong_inventory": records=[dict(records[0],html_url="https://github.com/other/repo/issues/1")]
  print(json.dumps([[],records]));sys.exit()
 print(json.dumps(pr if "/pulls/" in endpoint else issue));sys.exit()
'''
MOCK = PROJECT_MOCK.replace('if any(x.startswith("repos/") for x in args):', PROVIDER_READS + '\nif any(x.startswith("repos/") for x in args):')


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-observation-test-")
        self.dir = Path(self.tmp.name)
        self.mock = self.dir / "gh"
        self.mock.write_text(MOCK)
        self.mock.chmod(0o755)
        self.config = json.loads((ROOT / "local/github.json.example").read_text())
        self.config["repositories"]["nexus"]["repository"] = "a/b"
        self.config["repositories"]["nexus"]["project"].update(owner="a", number=1)
        self.cfg = self.dir / "config.json"
        self.save_config()
        self.calls = self.dir / "calls"
        self.env = dict(os.environ, NEXUS_GITHUB_OFFLINE_FIXTURE=str(self.mock),
                        NEXUS_GITHUB_CONFIG=str(self.cfg), MOCK_CALLS=str(self.calls),
                        MOCK_STATE=str(self.dir / "state"), ORCA_CLI_COMMAND="does-not-exist")

    def tearDown(self):
        self.tmp.cleanup()

    def save_config(self):
        self.cfg.write_text(json.dumps(self.config))

    def run_cli(self, *args, code=2):
        result = subprocess.run([str(ROOT / "scripts/observe.sh"), *args],
                                cwd=self.dir, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        for call in calls:
            self.assertFalse(any(x.startswith("query=mutation") for x in call), call)
            if "--method" in call:
                self.assertEqual(call[call.index("--method") + 1], "GET", call)
            self.assertNotIn("--input", call)
        return json.loads(result.stdout) if code == 2 else result

    def sources(self, bundle):
        return {s["name"]: s for s in bundle["sources"]}

    def test_complete_provider_reads_preserve_unknowns(self):
        bundle = self.run_cli("nexus", "1", "--pr", "3")
        sources = self.sources(bundle)
        self.assertTrue(bundle["requested_reads_complete"])
        self.assertEqual(set(sources), {"issue", "issues", "pull_requests", "comments", "project", "selected_pr", "review_checks"})
        self.assertEqual(len(sources["comments"]["data"]), 2)
        self.assertEqual(sources["review_checks"]["data"]["head_revision"], "a" * 40)
        self.assertEqual(bundle["project"]["status"], "Backlog")
        self.assertEqual(bundle["owner"]["issue_number"], "1")
        self.assertEqual(bundle["owner"]["work_item_id"], "https://github.com/a/b/issues/1")
        for source in sources.values():
            self.assertTrue(source["read_complete"])
            self.assertIsNone(source["inventory_complete"])
            self.assertIsNone(source["freshness_verified"])
            self.assertRegex(source["observed_at"], r"T\d\d:\d\d:\d\dZ$")
            self.assertIn("operation", source["source"])
        self.assertFalse(bundle["recovery_input_ready"])
        self.assertIsNone(bundle["backend"]["attempts"])
        self.assertEqual(bundle["backend"]["liveness"], "unknown")
        self.assertTrue(all(v is None for v in bundle["trust"].values()))
        self.assertIsNone(bundle["selection"]["association_verified"])

    def test_no_implicit_pr_selection_or_comment_trust(self):
        bundle = self.run_cli("nexus", "1")
        self.assertTrue(bundle["requested_reads_complete"])
        self.assertNotIn("selected_pr", self.sources(bundle))
        self.assertIsNone(bundle["selection"]["requested_pr_number"])
        self.assertNotIn('"pr", "view"', self.calls.read_text())
        self.assertIsNone(bundle["trust"]["human_decisions_verified"])

    def test_identity_and_malformed_sources_fail_closed(self):
        for mode, source in [("wrong_issue", "issue"), ("issue_is_pr", "issue"),
                             ("missing_timestamp", "issue"), ("wrong_inventory", "issues"),
                             ("wrong_comment", "comments"), ("truncated", "issue"),
                             ("error", "issue"), ("unavailable", "issue")]:
            with self.subTest(mode=mode):
                self.env["MOCK_OBS_MODE"] = mode
                bundle = self.run_cli("nexus", "1")
                self.assertFalse(bundle["requested_reads_complete"])
                failed = self.sources(bundle)[source]
                self.assertFalse(failed["read_complete"])
                self.assertIsNone(failed["data"])
                self.assertTrue(failed["diagnostics"])

    def test_absent_project_mapping_and_incomplete_project(self):
        self.config["repositories"]["nexus"].pop("project")
        self.save_config()
        bundle = self.run_cli("nexus", "1")
        self.assertFalse(bundle["project"]["known"])
        self.assertIsNone(bundle["project"]["status"])
        self.assertFalse(self.sources(bundle)["project"]["read_complete"])
        # Complete config but truncated outer Project pagination must also fail.
        self.config = json.loads((ROOT / "local/github.json.example").read_text())
        self.config["repositories"]["nexus"]["repository"] = "a/b"
        self.config["repositories"]["nexus"]["project"].update(owner="a", number=1)
        self.save_config()
        self.env["MOCK_ITEMS_INCOMPLETE"] = "1"
        self.assertFalse(self.run_cli("nexus", "1")["project"]["known"])

    def test_unknown_and_absent_project_membership(self):
        self.env["MOCK_EMPTY"] = "1"
        bundle = self.run_cli("nexus", "1")
        self.assertTrue(bundle["project"]["known"])
        self.assertTrue(bundle["project"]["membership_known"])
        self.assertFalse(bundle["project"]["member"])
        self.assertIsNone(bundle["project"]["status"])

    def test_stale_selected_pr_checks(self):
        self.env["MOCK_OBS_MODE"] = "stale_head"
        bundle = self.run_cli("nexus", "1", "--pr", "3")
        failed = self.sources(bundle)["review_checks"]
        self.assertEqual(failed["status"], "inconsistent")
        self.assertIsNone(failed["data"])
        self.assertFalse(bundle["requested_reads_complete"])

    def test_empty_transport_pages_never_certify_inventory(self):
        self.env["MOCK_OBS_MODE"] = "empty_pages"
        bundle = self.run_cli("nexus", "1")
        sources = self.sources(bundle)
        self.assertFalse(sources["issues"]["read_complete"])
        self.assertIsNone(sources["pull_requests"]["inventory_complete"])
        self.assertFalse(bundle["recovery_input_ready"])

    def test_help_and_bad_mapping_have_no_calls(self):
        self.run_cli("--help", code=0)
        self.assertFalse(self.calls.exists())
        for args in [("nexus", "0"), ("missing", "1"), ("nexus", "1", "--pr", "guess")]:
            self.run_cli(*args, code=1)
        self.cfg.write_text('{"version":1}\n{"version":1}')
        self.run_cli("nexus", "1", code=1)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
