"""Offline one-shot GitHub provider conformance; Python stdlib is development-only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/work-items.sh"
MOCK = '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ["MOCK_CALLS"],"a") as f: f.write(json.dumps(args)+"\\n")
if "pr" in args:
 if os.environ.get("MOCK_CHECKS") is not None:
  print(os.environ["MOCK_CHECKS"]); sys.exit()
 print(json.dumps({"url":"https://github.com/a/b/pull/2","headRefOid":"abc","reviewDecision":"APPROVED","statusCheckRollup":[{"name":"test","conclusion":"SUCCESS"},{"name":"build","conclusion":"FAILURE"}],"mergedAt":None,"isDraft":False})); sys.exit()
if "--input" in args:
 if os.environ.get("MOCK_FAIL"): sys.exit(1)
 payload=json.loads(Path(args[args.index("--input")+1]).read_text())
 if os.environ.get("MOCK_RESPONSE") is not None:
  print(os.environ["MOCK_RESPONSE"]); sys.exit()
 endpoint=next(x for x in args if x.startswith("repos/"))
 if endpoint.endswith("comments"):
  payload.update(id=3,html_url="https://github.com/a/b/issues/1#issuecomment-3",issue_url="https://api.github.com/repos/a/b/issues/1")
 elif "/pulls" in endpoint:
  head=payload["head"]; base=payload["base"]
  source="a/b" if ":" not in head else head.split(":")[0]+"/"+payload["head_repo"]
  branch=head.split(":")[-1]
  payload.update(number=2,html_url="https://github.com/a/b/pull/2",head={"label":head,"ref":branch,"repo":{"full_name":source},"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},base={"ref":base,"repo":{"full_name":"a/b"}})
 else:
  payload.update(number=1,html_url="https://github.com/a/b/issues/1")
  if "labels" in payload: payload["labels"]=[{"name":x} for x in payload["labels"]]
 print(json.dumps(payload)); sys.exit()
endpoint=next((x for x in args if x.startswith("repos/")), "")
if "/git/ref/heads/" in endpoint:
 if os.environ.get("MOCK_REF") is not None:
  print(os.environ["MOCK_REF"]); sys.exit()
 from urllib.parse import unquote
 source,branch=endpoint[6:].split("/git/ref/heads/",1); branch=unquote(branch)
 revision="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
 print(json.dumps({"ref":"refs/heads/"+branch,"url":"https://api.github.com/repos/"+source+"/git/refs/heads/"+branch,"object":{"type":"commit","sha":revision,"url":"https://api.github.com/repos/"+source+"/git/commits/"+revision}})); sys.exit()
if "--slurp" in args:
 print(json.dumps([json.loads(os.environ.get("MOCK_FOUND","[]"))])); sys.exit()
if os.environ.get("MOCK_READ") is not None:
 print(os.environ["MOCK_READ"]); sys.exit()
print(json.dumps({"html_url":"https://github.com/a/b/issues/1","number":1,"node_id":"I_1","title":"Issue","body":"Body","state":"open","updated_at":"t1","labels":[{"name":"ready"}]}))
'''

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-provider-test-")
        self.dir = Path(self.tmp.name)
        self.mock = self.dir / "gh"
        self.mock.write_text(MOCK)
        self.mock.chmod(0o755)
        self.calls = self.dir / "calls"
        self.env = dict(os.environ, NEXUS_GITHUB_OFFLINE_FIXTURE=str(self.mock), MOCK_CALLS=str(self.calls))
        self.request = self.dir / "request.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, good=True):
        r = subprocess.run([str(CLI), *args], cwd=ROOT, env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode == 0, good, r.stdout + r.stderr)
        return json.loads(r.stdout) if good else r

    def prepare(self, op="issue-create", **fields):
        request = {"operation_id":"op1", "title":"Title", "body":"Multiline\n`literal` $(not-shell)"}
        request.update(fields)
        self.request.write_text(json.dumps(request))
        return self.run_cli(op,"a/b",str(self.request))

    def apply(self, plan, op="issue-create", good=True):
        return self.run_cli(op,"a/b",str(self.request),"--apply","--approved-plan",plan["plan_oid"],"--approval-reference","human:test",good=good)

    def test_prepare_has_no_external_call(self):
        plan = self.prepare()
        self.assertFalse(plan["applied"])
        self.assertFalse(self.calls.exists())
        self.assertIn("$(not-shell)", plan["plan"]["payload"]["body"])

    def test_help_documents_pr_request_and_approval_without_provider(self):
        for command in [str(self.mock), str(self.dir / "missing-gh")]:
            with self.subTest(command=command):
                env = dict(self.env, NEXUS_GITHUB_OFFLINE_FIXTURE=command)
                result = subprocess.run([str(CLI), "--help"], cwd=ROOT, env=env,
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for text in ["pr-create", "operation_id: stable identifier",
                             "title: nonempty string; body: string",
                             "head_repository: OWNER/REPO", "forks supported",
                             "head: plain head branch name", "not OWNER:branch",
                             "base: target branch name",
                             "expected_head_revision: exact head SHA, 40 lowercase hexadecimal characters",
                             "draft: omitted or null defaults to true; explicit false is preserved",
                             "Only booleans or null are accepted; other values are rejected",
                             "--apply --approved-plan OID --approval-reference TEXT",
                             "exact prepared plan_oid", "explicit human\npublication approval",
                             "Changed requests require a newly approved plan"]:
                    self.assertIn(text, result.stdout)
                self.assertFalse(self.calls.exists())

    def test_exact_apply_and_changed_payload(self):
        plan = self.prepare()
        result = self.apply(plan)
        self.assertTrue(result["applied"])
        self.assertIn("nexus-operation:op1", result["record"]["body"])
        request=json.loads(self.request.read_text()); request["title"]="Changed"
        self.request.write_text(json.dumps(request))
        self.apply(plan,good=False)

    def test_no_approval_no_write(self):
        self.prepare()
        self.run_cli("issue-create","a/b",str(self.request),"--apply",good=False)
        self.assertFalse(self.calls.exists())

    def test_read_identity_and_checks(self):
        item=self.run_cli("issue-read","a/b","1")
        self.assertEqual(item["id"],"https://github.com/a/b/issues/1")
        checks=self.run_cli("review-checks-read","a/b","2")
        self.assertEqual(checks["review_state"],"approved")
        self.assertEqual([x["state"] for x in checks["checks"]],["pass","fail"])

    def test_recovered_create_no_second_write_and_conflict(self):
        plan=self.prepare()
        prior=dict(plan["plan"]["payload"], number=1, html_url="https://github.com/a/b/issues/1")
        self.env["MOCK_FOUND"]=json.dumps([prior])
        self.assertTrue(self.apply(plan)["recovered"])
        calls=[json.loads(x) for x in self.calls.read_text().splitlines()]
        self.assertFalse(any("--input" in x for x in calls))
        prior["title"]="Conflicting operation"
        self.env["MOCK_FOUND"]=json.dumps([prior])
        self.apply(plan,good=False)

    def test_stale_update_and_ambiguous_failure(self):
        plan=self.prepare("issue-update",number=1,expected_updated_at="stale",changes={"labels":["review"]})
        self.apply(plan,"issue-update",good=False)
        plan=self.prepare()
        self.env["MOCK_FAIL"]="1"
        self.apply(plan,good=False)
        calls=[json.loads(x) for x in self.calls.read_text().splitlines()]
        self.assertEqual(sum("--input" in x for x in calls),1)

    def test_ambiguous_and_wrong_identity_write_responses(self):
        plan=self.prepare()
        for response in [{}, {"number":1,"html_url":"https://github.com/other/repo/issues/1"},
                         {"number":1,"html_url":"https://github.com/a/b/issues/1","title":"Wrong","body":"Wrong"}]:
            self.env["MOCK_RESPONSE"]=json.dumps(response)
            self.apply(plan,good=False)

    def test_pr_comment_and_successful_update(self):
        plan=self.prepare("pr-create",head="feature",base="main",head_repository="a/b",expected_head_revision="a"*40)
        self.assertTrue(self.apply(plan,"pr-create")["applied"])
        plan=self.prepare("association-comment",number=1,expected_updated_at="t1")
        self.assertTrue(self.apply(plan,"association-comment")["applied"])
        plan=self.prepare("issue-update",number=1,expected_updated_at="t1",changes={"labels":["review"]})
        self.assertTrue(self.apply(plan,"issue-update")["applied"])

    def pr_plan(self, **fields):
        request = dict(head="feature", base="main", head_repository="a/b", expected_head_revision="a"*40)
        request.update(fields)
        return self.prepare("pr-create", **request)

    def write_calls(self):
        calls = [json.loads(x) for x in self.calls.read_text().splitlines()] if self.calls.exists() else []
        return [x for x in calls if "--input" in x]

    def pr_record(self, plan, **changes):
        record = dict(plan["plan"]["payload"], number=2, html_url="https://github.com/a/b/pull/2",
                      head={"ref":plan["plan"]["candidate"]["branch"], "repo":{"full_name":plan["plan"]["candidate"]["repository"]}, "sha":"a"*40},
                      base={"ref":"main", "repo":{"full_name":"a/b"}})
        record.update(changes)
        return record

    def test_pr_candidate_bound_and_required(self):
        first = self.pr_plan()
        second = self.pr_plan(expected_head_revision="b"*40)
        self.assertNotEqual(first["plan_oid"], second["plan_oid"])
        self.assertEqual(first["plan"]["candidate"]["revision"], "a"*40)
        self.apply(first, "pr-create", good=False)
        self.assertFalse(self.calls.exists())
        for fields in [{"expected_head_revision":None}, {"head_repository":None}, {"expected_head_revision":"abc"}, {"head_repository":"../b"}, {"head":"owner:feature"}, {"head":"main"}]:
            request=dict(operation_id="op1", title="Title", body="Body", head="feature", base="main", head_repository="a/b", expected_head_revision="a"*40)
            request.update(fields)
            request = {key:value for key,value in request.items() if value is not None}
            self.request.write_text(json.dumps(request))
            self.run_cli("pr-create","a/b",str(self.request),good=False)
        self.assertFalse(self.calls.exists())

    def test_pr_moved_or_wrong_source_precheck_never_writes(self):
        plan = self.pr_plan()
        for ref in [{"ref":"refs/heads/feature","url":"https://api.github.com/repos/a/b/git/refs/heads/feature","object":{"type":"commit","sha":"b"*40,"url":"https://api.github.com/repos/a/b/git/commits/"+"b"*40}},
                    {"ref":"refs/heads/feature","object":{"type":"commit","sha":"a"*40}}]:
            self.env["MOCK_REF"] = json.dumps(ref)
            self.apply(plan,"pr-create",good=False)
        self.assertEqual(self.write_calls(), [])

    def test_pr_wrong_returned_and_recovered_head_rejected(self):
        plan = self.pr_plan()
        bad = self.pr_record(plan, head={"ref":"feature", "repo":{"full_name":"a/b"}, "sha":"b"*40})
        self.env["MOCK_RESPONSE"] = json.dumps(bad)
        self.apply(plan,"pr-create",good=False)
        self.assertEqual(len(self.write_calls()),1)
        self.env["MOCK_FOUND"] = json.dumps([bad])
        self.apply(plan,"pr-create",good=False)
        self.assertEqual(len(self.write_calls()),1)
        self.env["MOCK_FOUND"] = json.dumps([self.pr_record(plan)])
        self.assertTrue(self.apply(plan,"pr-create")["recovered"])
        self.assertEqual(len(self.write_calls()),1)

    def test_pr_exact_fork_and_slash_branch(self):
        plan = self.pr_plan(head="topic/change", head_repository="fork/b")
        self.assertEqual(plan["plan"]["payload"]["head"],"fork:topic/change")
        self.assertTrue(self.apply(plan,"pr-create")["applied"])
        bad = self.pr_record(plan, head={"ref":"topic/change", "repo":{"full_name":"other/b"}, "sha":"a"*40})
        self.env["MOCK_FOUND"] = json.dumps([bad])
        self.apply(plan,"pr-create",good=False)
        self.assertEqual(len(self.write_calls()),1)

    def issue_record(self, **changes):
        record = dict(html_url="https://github.com/a/b/issues/1", number=1, node_id="I_1",
                      title="Issue", body="Body", state="open", updated_at="t1", labels=[])
        record.update(changes)
        return record

    def test_single_reads_reject_wrong_repo_number_kind_and_identity(self):
        for record in [self.issue_record(html_url="https://github.com/c/d/issues/2",number=2),
                       self.issue_record(html_url="https://github.com/a/b/issues/2",number=2),
                       self.issue_record(html_url="https://github.com/A/b/issues/1"),
                       self.issue_record(number=None), self.issue_record(number=1.5),
                       self.issue_record(pull_request={}), self.issue_record(html_url="https://github.com/a/b/pull/1")]:
            self.env["MOCK_READ"] = json.dumps(record)
            self.run_cli("issue-read","a/b","1",good=False)
        self.env["MOCK_READ"] = json.dumps(self.issue_record(html_url="https://github.com/a/b/pull/1"))
        self.assertEqual(self.run_cli("pr-read","a/b","1")["kind"], "pull-request")
        self.run_cli("pr-read","a/b","2",good=False)
        self.assertEqual(self.write_calls(), [])

    def test_lists_check_ownership_and_positive_identity(self):
        self.env["MOCK_FOUND"] = json.dumps([self.issue_record()])
        self.assertEqual(len(self.run_cli("issue-list","a/b")),1)
        for record in [self.issue_record(html_url="https://github.com/c/d/issues/1"), self.issue_record(number=0)]:
            self.env["MOCK_FOUND"] = json.dumps([record])
            self.run_cli("issue-list","a/b",good=False)
        self.env["MOCK_FOUND"] = json.dumps([self.issue_record(html_url="https://github.com/a/b/pull/1")])
        self.assertEqual(len(self.run_cli("pr-list","a/b")),1)
        self.env["MOCK_FOUND"] = json.dumps([self.issue_record(html_url="https://github.com/c/d/pull/1")])
        self.run_cli("pr-list","a/b",good=False)
        self.assertEqual(self.write_calls(), [])

    def test_transferred_issue_blocks_updates_comments_and_recovery_before_write(self):
        for op in ["issue-update", "association-comment"]:
            for record in [self.issue_record(html_url="https://github.com/c/d/issues/2",number=2),
                           self.issue_record(html_url="https://github.com/a/b/issues/2",number=2),
                           self.issue_record(pull_request={})]:
                plan = self.prepare(op, number=1, expected_updated_at="t1", changes={"title":"New"})
                self.env["MOCK_READ"] = json.dumps(record)
                self.apply(plan,op,good=False)
                self.assertEqual(self.write_calls(), [])
        plan = self.prepare("association-comment",number=1,expected_updated_at="t1")
        self.env["MOCK_FOUND"] = json.dumps([dict(plan["plan"]["payload"],id=3,
            html_url="https://github.com/a/b/issues/1#issuecomment-3",issue_url="https://api.github.com/repos/a/b/issues/1")])
        self.apply(plan,"association-comment",good=False)
        self.env["MOCK_READ"] = json.dumps(self.issue_record(updated_at="newer"))
        self.assertTrue(self.apply(plan,"association-comment")["recovered"])
        self.assertEqual(self.write_calls(), [])

    def test_association_read_and_review_checks_verify_target(self):
        self.env["MOCK_READ"] = json.dumps(self.issue_record(html_url="https://github.com/c/d/issues/2",number=2))
        self.run_cli("association-read","a/b","1",good=False)
        self.env["MOCK_READ"] = json.dumps(self.issue_record())
        self.env["MOCK_FOUND"] = json.dumps([dict(id=3,body="link",user={"login":"human"},
            html_url="https://github.com/a/b/issues/1#issuecomment-3",issue_url="https://api.github.com/repos/a/b/issues/1")])
        self.assertEqual(len(self.run_cli("association-read","a/b","1")),1)
        self.env["MOCK_FOUND"] = json.dumps([dict(id=3,html_url="https://github.com/c/d/issues/1#issuecomment-3",issue_url="https://api.github.com/repos/c/d/issues/1")])
        self.run_cli("association-read","a/b","1",good=False)
        self.env["MOCK_CHECKS"] = json.dumps(dict(url="https://github.com/c/d/pull/2"))
        self.run_cli("review-checks-read","a/b","2",good=False)
        self.assertEqual(self.write_calls(), [])

    def test_pr_draft_boolean_prepare_apply_and_recovery(self):
        for fields, expected in [({},True), ({"draft":None},True), ({"draft":False},False), ({"draft":True},True)]:
            with self.subTest(fields=fields):
                self.env.pop("MOCK_FOUND",None)
                plan = self.pr_plan(**fields)
                self.assertIs(plan["plan"]["payload"]["draft"],expected)
                self.assertTrue(self.apply(plan,"pr-create")["applied"])
                writes = len(self.write_calls())
                self.env["MOCK_FOUND"] = json.dumps([self.pr_record(plan)])
                self.assertTrue(self.apply(plan,"pr-create")["recovered"])
                self.assertEqual(len(self.write_calls()),writes)
                self.env["MOCK_FOUND"] = json.dumps([self.pr_record(plan,draft=not expected)])
                self.apply(plan,"pr-create",good=False)
                self.assertEqual(len(self.write_calls()),writes)

    def test_pr_draft_invalid_types_rejected_without_api(self):
        for value in ["false", "true", 0, 1, [], {}]:
            request=dict(operation_id="op1",title="Title",body="Body",head="feature",base="main",
                         head_repository="a/b",expected_head_revision="a"*40,draft=value)
            self.request.write_text(json.dumps(request))
            self.run_cli("pr-create","a/b",str(self.request),good=False)
        self.assertFalse(self.calls.exists())

    def test_pr_draft_change_invalidates_approval(self):
        first = self.pr_plan(draft=False)
        second = self.pr_plan(draft=True)
        self.assertNotEqual(first["plan_oid"],second["plan_oid"])
        self.apply(first,"pr-create",good=False)
        self.assertFalse(self.calls.exists())

    def test_invalid_target_and_unsupported_operation(self):
        self.run_cli("issue-list","../b",good=False)
        self.run_cli("merge","a/b",good=False)
        self.assertFalse(self.calls.exists())

if __name__ == "__main__":
    unittest.main()
