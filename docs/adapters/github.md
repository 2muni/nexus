# GitHub Work Item provider

`schemas/work-item-provider.yaml` defines logical Work Items; GitHub is the only current
provider. `scripts/work-items.sh` is a one-operation CLI binding, not a workflow daemon.
It uses one-shot GitHub App installation authentication through installed `gh` and
`jq` for structured JSON; it never loads Orca. Configure the ignored local App
binding and external key as described in [authentication](../github-app-authentication.md).
Both API and PR review/check reads use this boundary, without personal credentials.
Issue identity is its canonical GitHub URL. Native node IDs remain adapter metadata.
Single reads bind repository, record kind and number to the returned canonical URL;
lists enforce repository/kind and positive number for every record. Comment and PR
review/check reads verify their canonical targets too. Update/comment applies validate
Issue identity before lookup/recovery or writes; timestamp freshness is additionally
required before a new write. Empty comment lists do not prove target identity.
Transferred Issues, renames and case-only aliases are rejected rather than silently
adopting new ownership. Reobserve the canonical repository/name/number, explicitly
remap the Work Item and prepare a newly approved target plan. Use canonical spelling;
this intentionally fails closed even though GitHub accepts case-insensitive names.
The read/write race still requires one Coordinator writer; identity checks are not CAS.

Read: `issue-read`, `issue-list`, `pr-read`, `pr-list`, `review-checks-read` with explicit
OWNER/REPO and (for item reads) a positive number. List results are complete paginated
normalized Work Items; review/check reads normalize review and check observations,
not automatic acceptance. Native details remain opaque adapter metadata. Missing reviews/checks is not PASS.

Write: `issue-create`, `issue-update`, `pr-create`, `association-comment` take a JSON file.
All require `operation_id`; creates also title/body, PRs explicit branch names head/base, head_repository (OWNER/REPO), and
expected_head_revision (40 lowercase hexadecimal characters);
updates/comments require number and expected_updated_at. Issue changes support title,
body, labels, milestone and state. Preserve current human content when constructing a
body update. PR draft defaults to true for omitted/null; explicit false is preserved,
and other types are rejected before any API call. Both draft and non-draft PRs require
published head branches, but this tool never pushes.
Association comments carry reviewed sanitized task/attempt/backend/PR associations.

By default a write returns a prepared plan and its Git blob `plan_oid` without an API write.
After the exact plan has human authorization, apply with `--apply --approved-plan OID
--approval-reference REF`. The reference names the real human decision; supplying a string
cannot create authority. Repo/action/payload changes invalidate the digest. User authorization
to implement/commit Nexus does not authorize publishing Issues, PRs or comments.

One Coordinator owns writes to a Work Item. Updates recheck expected_updated_at, but this
is not atomic CAS: stop if concurrent writers exist. Creates/comments use a stable operation
marker and lookup every page before writing. A matching prior result is recovered without
another write; contradictory markers require reconciliation. PR plans include the exact
source repository/branch/revision separately from the API payload. Fork payloads use
owner:branch and head_repo; callers supply the unqualified branch in head. The adapter
checks the exact remote source ref before registration and requires the same source,
revision and base repository in returned/recovered PRs. Branch/revision changes require
new approval. This intentionally rejects old PR requests lacking candidate identity.
The ref lookup and PR POST are not atomic: strict exact-diff publication requires a
controlled dedicated source branch with one writer through registration. A mismatched
post-write head is HOLD/reconciliation, not success, and cannot undo an already published
PR. The base branch may also move; this binding pins source head, not an immutable base
comparison or merge authorization. On timeout/error preserve the
plan and inspect external state; never automate a retry or presume an absent lookup proves
absence. GitHub mutations are not globally transactional or guaranteed exactly-once.

A durable association comment records schema version, Work Item URL, logical task and
attempt IDs, selected backend, sanitized external receipt reference, exact artifact/head
revision, PR URL, validation result/evidence reference and applicable human approval scope.
It excludes machine paths, credentials, transcripts and private report contents. Store only
human-reviewed metadata. Human edits and PR merge/check outcomes remain authoritative.

Default is one Issue/Work Item/mutable worktree/PR. Keep remediation attempts under the same
Issue; record linked splits for independently reviewable scope. GitHub record open/closed
state is distinct from the six-state workflow. Projects status is added separately.
No merge, push, deletion or automatic Project/Issue publication is implemented.

API behavior is grounded in installed `gh api` help and
[GitHub Issues REST documentation](https://docs.github.com/en/rest/issues/issues) and
[Pull Requests REST documentation](https://docs.github.com/en/rest/pulls/pulls).
Provider conformance tests use the explicit unauthenticated offline fixture boundary;
App tests use generated temporary keys and mocked HTTP. No remote Issue/PR was created
for verification. Live read validation and current-head review/CI remain separate evidence.
