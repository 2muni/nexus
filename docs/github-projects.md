# Repository-specific GitHub Projects

Each logical repository maps to its own GitHub repository and linked Project in ignored
`local/github.json`; copy `local/github.json.example` and set the real Project number.
Do not share a configured Project among repository owners, including owner case aliases. The owning repository handles
its Work Items; Nexus coordinates dependencies across normalized inputs. This maintenance
run configures only Nexus, never another repository's board.

GitHub Projects are user/organization-owned and linked to repositories. A repository's
`/projects` page is a listing, not the Project number/URL. Inspect the exact user/org Project
and its repository link. Provider calls use [one-shot App authentication](github-app-authentication.md)
with exact owning-repository context; personal `gh` credentials are never a fallback.
Project reads/mutations need existing organization Projects read/write grants respectively;
unsupported user-owned Projects fail closed without changing App registration.
No key or token plaintext belongs in local mappings or reports.

`scripts/projects.sh read nexus` reads a complete paginated field/item inventory and emits
canonical workflow status and priority. `item-add nexus request.json` prepares membership
of an existing Issue in the configured Project. Its only request property is `issue_url`:

```json
{"issue_url":"https://github.com/OWNER/REPO/issues/NUMBER"}
```

The URL must identify an Issue in the exact configured repository. The adapter reads the
Issue to verify its canonical URL, number and provider node ID; a PR, redirected/mismatched
Issue or incomplete identity is rejected. The plan binds the exact Project and Issue IDs.
Apply uses the existing `--apply --approved-plan OID --approval-reference REF` boundary;
the reference must name a real human authorization, not an invented CLI string. Membership
presence is excluded from the digest so that a later observation can settle the same plan.
Existing unique membership is unchanged with no write. Duplicate/conflicting identities
or incomplete pagination HOLD. Retain one Coordinator writer; prechecks are not atomic CAS.

One add mutation is followed by a complete fresh snapshot. A matching identified response
plus exact observed membership returns `applied:true, observed:true`. Lost/empty/ambiguous
responses with exact observed membership return `applied:false, recovered:true, observed:true`:
the requested state exists, but that mutation's success is not certified. Contradictory
identified responses or absent membership HOLD. No blind retry or deletion compensates an
unknown response; preserve the plan and reobserve before any new explicit decision.
Registration does not set Workflow or Priority, create an Issue, or start an agent. GitHub
itself may have human-configured Project automation; observe its field values rather than
overwriting them. Separate field plans are required after membership is verified.

`field-update nexus request.json` prepares an exact
single-field write plan. Requests specify Issue URL, status/priority, expected current value
(or null for an unset field), and desired canonical value. Actual writes require matching
plan digest and real human approval reference. Reobserve after mutation; a successful
transport alone is not completion. A repeat already at the desired value does not write.
Changed/unmapped human values, missing options, duplicate items or incomplete inventory HOLD.
Both outer field/item page chains must finish explicitly; truncated/error pages cannot
produce an update plan even if the desired item appears on a partial page.
Pre-write comparisons are not atomic CAS; retain one Coordinator writer and reobserve
concurrent human changes rather than claiming transactional synchronization.

The configured canonical status field must expose six distinct values: Backlog, Ready,
In Progress, Blocked, Review, Done. Priority supports P0–P3. Native field/option IDs and
names are adapter metadata; core workflow uses logical fields and values. The field may
be named `Workflow` to preserve GitHub's default Status field; in that case Workflow is
the sole Nexus-authoritative lifecycle field, and the default field is unmanaged display
metadata. Configure table/board grouping to use Workflow; never read the default field as
a competing lifecycle source. Existing projects may instead map their canonical Status field.

The Coordinator evaluates a fresh observation with `scripts/workflow.sh`, then prepares
only an authorized Project field change. Proposed transitions do not claim updates occurred.
Human changes must be observed first. No automatic Project creation, Issue publication,
merge, scheduling or retry is added by this tool.

Project setup and linked-board reads have been verified in the maintenance environment;
account-specific mappings remain ignored local configuration. Local fixtures verify membership,
fields/options, owner isolation,
stale values, exact approvals, mutation response identity, reobservation and idempotent
updates. Live registration/field synchronization needs an exact-approved existing Issue;
none is fabricated or published by the offline tests.

Implementation follows the installed GitHub CLI and
[GitHub Projects API guidance](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).
Membership uses the documented
[addProjectV2ItemById mutation](https://docs.github.com/en/graphql/reference/projects#addprojectv2itembyid).
