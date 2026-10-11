"""Offline Project mapping and exact-plan write conformance."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
MOCK='''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ["MOCK_CALLS"],"a") as f: f.write(json.dumps(args)+"\\n")
state=Path(os.environ["MOCK_STATE"])
if any(x.startswith("repos/") for x in args):
 issue={"html_url":"https://github.com/a/b/issues/1","number":1,"node_id":"issue1"}
 if os.environ.get("MOCK_PR"): issue["pull_request"]={}
 if os.environ.get("MOCK_WRONG_ISSUE"): issue["html_url"]="https://github.com/a/b/issues/2"
 if os.environ.get("MOCK_MISSING_NODE"): issue.pop("node_id")
 if os.environ.get("MOCK_CHANGED_NODE"): issue["node_id"]="issue2"
 print(json.dumps(issue));sys.exit()
query=next(x[6:] for x in args if x.startswith("query="))
if query.startswith("mutation"):
 if "addProjectV2ItemById" in query:
  if not os.environ.get("MOCK_NO_MEMBERSHIP"): state.write_text("Backlog")
  if os.environ.get("MOCK_TIMEOUT"): print("lost response",file=sys.stderr);sys.exit(1)
  if os.environ.get("MOCK_BAD_RESPONSE"): print("{}");sys.exit()
  if os.environ.get("MOCK_GRAPHQL_ERROR"): print(json.dumps({"errors":[{"message":"ambiguous"}]}));sys.exit()
  item={"id":"item1","project":{"id":"project1"},"content":{"id":"issue1","url":"https://github.com/a/b/issues/1","repository":{"nameWithOwner":"a/b"}}}
  if os.environ.get("MOCK_WRONG_RESULT"): item["project"]["id"]="project2"
  if os.environ.get("MOCK_WRONG_ITEM"): item["id"]="item2"
  print(json.dumps({"data":{"addProjectV2ItemById":{"item":item}}}));sys.exit()
 state.write_text("Ready")
 if os.environ.get("MOCK_BAD_RESPONSE"): print("{}");sys.exit()
 print(json.dumps({"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"item1"}}}}));sys.exit()
if "owner:" in query:
 print(json.dumps({"data":{"owner":{"projectV2":{"id":"project1","number":1,"url":"https://github.com/users/a/projects/1","title":"Nexus","repositories":{"nodes":[{"nameWithOwner":"a/b"}],"pageInfo":{"hasNextPage":False}}}}}}));sys.exit()
if "fields(first" in query:
 names=["Backlog","Ready","In Progress","Blocked","Review","Done"]
 fields=[{"id":"field1","name":"Workflow","options":[{"id":n,"name":n} for n in names]}, {"id":"field2","name":"Priority","options":[{"id":n,"name":n} for n in ["P0","P1","P2","P3"]]}]
 if os.environ.get("MOCK_BAD_FIELD"): fields=fields[1:]
 print(json.dumps([{"data":{"node":{"fields":{"nodes":fields,"pageInfo":{"hasNextPage":bool(os.environ.get("MOCK_FIELDS_INCOMPLETE")),"endCursor":None}}}}}])) ;sys.exit()
value=state.read_text() if state.exists() else "Backlog"
item={"id":"item1","content":{"id":"issue1","url":"https://github.com/a/b/issues/1","repository":{"nameWithOwner":"a/b"}},"fieldValues":{"nodes":[{"name":value,"optionId":value,"field":{"id":"field1","name":"Workflow"}}],"pageInfo":{"hasNextPage":bool(os.environ.get("MOCK_ITEM_FIELDS_INCOMPLETE"))}}}
if os.environ.get("MOCK_CONFLICTING_MEMBER"): item["content"]["id"]="other"
if os.environ.get("MOCK_MEMBER_URL_CHANGED"): item["content"]["url"]="https://github.com/a/b/issues/2"
items=[] if os.environ.get("MOCK_EMPTY") and not state.exists() else [item]
if os.environ.get("MOCK_DUPLICATE"): items=[item,item]
page={"data":{"node":{"items":{"nodes":items,"pageInfo":{"hasNextPage":bool(os.environ.get("MOCK_ITEMS_INCOMPLETE")),"endCursor":None}}}}}
pages=[page]
if os.environ.get("MOCK_LATE_PAGE"):
 first={"data":{"node":{"items":{"nodes":[],"pageInfo":{"hasNextPage":True,"endCursor":"page2"}}}}}
 pages=[first,page]
print(json.dumps(pages))
'''
class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nexus-project-test-"); self.dir=Path(self.tmp.name)
        self.mock=self.dir/"gh";self.mock.write_text(MOCK);self.mock.chmod(0o755)
        self.config=json.loads((ROOT/"local/github.json.example").read_text())
        self.config["repositories"]["nexus"]["repository"]="a/b"
        self.config["repositories"]["nexus"]["project"].update(owner="a",number=1)
        self.cfg=self.dir/"config.json";self.cfg.write_text(json.dumps(self.config))
        self.req=self.dir/"request.json";self.req.write_text(json.dumps(dict(issue_url="https://github.com/a/b/issues/1",field="status",expected_value="Backlog",value="Ready")))
        self.calls=self.dir/"calls";self.state=self.dir/"state"
        self.env=dict(os.environ,NEXUS_GITHUB_OFFLINE_FIXTURE=str(self.mock),NEXUS_GITHUB_CONFIG=str(self.cfg),MOCK_CALLS=str(self.calls),MOCK_STATE=str(self.state))
    def tearDown(self): self.tmp.cleanup()
    def run_cli(self,*args,good=True):
        r=subprocess.run([str(ROOT/"scripts/projects.sh"),*args],cwd=ROOT,env=self.env,text=True,capture_output=True)
        self.assertEqual(r.returncode==0,good,r.stdout+r.stderr)
        return json.loads(r.stdout) if good else r
    def writes(self):
        return sum(any(x.startswith("query=mutation") for x in json.loads(line)) for line in self.calls.read_text().splitlines()) if self.calls.exists() else 0

class ProjectTests(ProjectFixture):
    def test_read_normalizes_and_prepare_no_write(self):
        s=self.run_cli("read","nexus");self.assertEqual(s["work_items"][0]["fields"]["status"],"Backlog")
        p=self.run_cli("field-update","nexus",str(self.req));self.assertFalse(p["applied"]);self.assertEqual(self.writes(),0)
    def test_exact_apply_reobserves_and_repeat_no_write(self):
        p=self.run_cli("field-update","nexus",str(self.req))
        args=("field-update","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1")
        result=self.run_cli(*args);self.assertTrue(result["observed"]);self.assertEqual(self.writes(),1)
        self.assertTrue(self.run_cli(*args)["unchanged"]);self.assertEqual(self.writes(),1)
    def test_stale_and_wrong_repository(self):
        self.state.write_text("Review");self.run_cli("field-update","nexus",str(self.req),good=False);self.assertEqual(self.writes(),0)
        request=json.loads(self.req.read_text());request["issue_url"]="https://github.com/other/repo/issues/1";self.req.write_text(json.dumps(request))
        self.run_cli("field-update","nexus",str(self.req),good=False)
    def test_missing_fields_and_shared_board(self):
        self.env["MOCK_BAD_FIELD"]="1";self.run_cli("read","nexus",good=False)
        self.env.pop("MOCK_BAD_FIELD");self.config["repositories"]["foundry"]=self.config["repositories"]["nexus"]
        self.cfg.write_text(json.dumps(self.config));self.run_cli("read","nexus",good=False)
    def test_incomplete_outer_pagination_and_case_alias_board(self):
        for flag in ["MOCK_FIELDS_INCOMPLETE","MOCK_ITEMS_INCOMPLETE"]:
            self.env[flag]="1"
            self.run_cli("field-update","nexus",str(self.req),good=False)
            self.assertEqual(self.writes(),0)
            self.env.pop(flag)
        other=json.loads(json.dumps(self.config["repositories"]["nexus"]))
        other["project"]["owner"]="A"
        self.config["repositories"]["foundry"]=other
        self.cfg.write_text(json.dumps(self.config))
        self.run_cli("read","nexus",good=False)

    def test_unconfigured_no_api_and_ambiguous_mutation(self):
        p=self.run_cli("field-update","nexus",str(self.req));self.env["MOCK_BAD_RESPONSE"]="1"
        self.run_cli("field-update","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1",good=False)
        self.assertEqual(self.writes(),1)
        self.config["repositories"]["nexus"]["project"]["number"]=None;self.cfg.write_text(json.dumps(self.config))
        self.run_cli("read","nexus",good=False)

class MembershipTests(ProjectFixture):
    def setUp(self):
        super().setUp()
        self.req.write_text(json.dumps(dict(issue_url="https://github.com/a/b/issues/1")))
        self.env["MOCK_EMPTY"]="1"
    # Only membership scenarios; field tests use ProjectTests' own fixture.
    def test_prepare_and_exact_apply_then_same_plan_noop(self):
        p=self.run_cli("item-add","nexus",str(self.req))
        self.assertFalse(p["already_member"]);self.assertEqual(self.writes(),0)
        args=("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1")
        r=self.run_cli(*args);self.assertTrue(r["applied"]);self.assertTrue(r["observed"])
        self.assertTrue(self.run_cli(*args)["unchanged"]);self.assertEqual(self.writes(),1)
        self.assertEqual(self.run_cli("item-add","nexus",str(self.req))["plan_oid"],p["plan_oid"])
    def test_existing_membership_on_later_page_no_write(self):
        self.env.pop("MOCK_EMPTY");self.env["MOCK_LATE_PAGE"]="1"
        p=self.run_cli("item-add","nexus",str(self.req));self.assertTrue(p["already_member"])
        r=self.run_cli("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1")
        self.assertTrue(r["unchanged"]);self.assertEqual(self.writes(),0)
    def test_registration_preserves_fields_then_separate_update(self):
        p=self.run_cli("item-add","nexus",str(self.req))
        self.run_cli("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:register")
        self.assertEqual(self.run_cli("read","nexus")["work_items"][0]["fields"],dict(status="Backlog",priority=None))
        self.req.write_text(json.dumps(dict(issue_url="https://github.com/a/b/issues/1",field="status",expected_value="Backlog",value="Ready")))
        p=self.run_cli("field-update","nexus",str(self.req))
        self.run_cli("field-update","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:status")
        self.assertEqual(self.run_cli("read","nexus")["work_items"][0]["fields"]["status"],"Ready")
        self.assertEqual(self.writes(),2)
    def test_absent_or_stale_authorization_never_writes(self):
        self.run_cli("item-add","nexus",str(self.req),"--apply",good=False)
        p=self.run_cli("item-add","nexus",str(self.req))
        args=("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1")
        self.env["MOCK_CHANGED_NODE"]="1";self.run_cli(*args,good=False);self.assertEqual(self.writes(),0)
        self.env.pop("MOCK_CHANGED_NODE")
        self.run_cli("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","   ",good=False)
        self.assertEqual(self.writes(),0)
    def test_canonical_issue_identity_and_no_extra_changes(self):
        for url in ["https://github.com/x/y/issues/1","https://github.com/a/b/pull/1","https://github.com/a/b/issues/01","https://github.com/a/b/issues/1?x=1"]:
            self.req.write_text(json.dumps(dict(issue_url=url)));self.run_cli("item-add","nexus",str(self.req),good=False)
        self.req.write_text(json.dumps(dict(issue_url="https://github.com/a/b/issues/1",value="Ready")))
        self.run_cli("item-add","nexus",str(self.req),good=False)
        self.req.write_text(json.dumps(dict(issue_url="https://github.com/a/b/issues/1")))
        for flag in ["MOCK_PR","MOCK_WRONG_ISSUE","MOCK_MISSING_NODE"]:
            self.env[flag]="1";self.run_cli("item-add","nexus",str(self.req),good=False);self.env.pop(flag)
        self.assertEqual(self.writes(),0)
    def test_incomplete_duplicate_or_conflicting_inventory_holds(self):
        for flag in ["MOCK_FIELDS_INCOMPLETE","MOCK_ITEMS_INCOMPLETE","MOCK_ITEM_FIELDS_INCOMPLETE","MOCK_DUPLICATE","MOCK_CONFLICTING_MEMBER","MOCK_MEMBER_URL_CHANGED"]:
            self.env.pop("MOCK_EMPTY",None);self.env[flag]="1"
            self.run_cli("item-add","nexus",str(self.req),good=False);self.env.pop(flag)
        self.assertEqual(self.writes(),0)
    def test_unknown_response_recovers_only_from_complete_membership(self):
        for flag in ["MOCK_TIMEOUT","MOCK_BAD_RESPONSE","MOCK_GRAPHQL_ERROR"]:
            if self.state.exists(): self.state.unlink()
            self.env[flag]="1"
            p=self.run_cli("item-add","nexus",str(self.req))
            before=self.writes()
            args=("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1")
            r=self.run_cli(*args);self.assertTrue(r["recovered"]);self.assertFalse(r["applied"]);self.assertTrue(r["observed"])
            self.assertTrue(self.run_cli(*args)["unchanged"]);self.assertEqual(self.writes(),before+1)
            self.env.pop(flag)
    def test_unobserved_or_contradictory_response_is_not_success(self):
        for flag in ["MOCK_NO_MEMBERSHIP","MOCK_WRONG_RESULT","MOCK_WRONG_ITEM"]:
            if self.state.exists(): self.state.unlink()
            self.env[flag]="1"
            p=self.run_cli("item-add","nexus",str(self.req));before=self.writes()
            self.run_cli("item-add","nexus",str(self.req),"--apply","--approved-plan",p["plan_oid"],"--approval-reference","human:1",good=False)
            self.assertEqual(self.writes(),before+1);self.env.pop(flag)
if __name__=="__main__": unittest.main()
