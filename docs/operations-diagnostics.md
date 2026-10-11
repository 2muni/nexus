# Read-only operations diagnostics

Use this procedure at intake, a supervision checkpoint or restart to compare current
intent with facts. [Nexus owns workflow, GitHub owns durable state and the execution
backend owns attempt observations](operating-model.md). Read [operator workflow](operator-workflow.md),
[acceptance policy](acceptance-policy.md) and [review principles](review-principles.md)
before deciding readiness. Existing diagnostics gather evidence; the Coordinator
still owns the decision and exact human controls.

## Establish the observation scope

Record the canonical Issue, logical owner, known PRs, inspected revision, observation
window, relevant retained checkouts and applicable policy provenance in ignored
`reviews/` or `.runtime/`. Inspect the assigned checkout before any action:

```bash
git rev-parse --show-toplevel
git rev-parse HEAD
git status --short --untracked-files=all
./scripts/doctor.sh nexus
./scripts/status.sh
```

Run from the intended Nexus checkout; substitute another registered owner only when
that owner is in scope. Compare the exact base and identity with the assignment.
Explicitly include a frozen snapshot of dirty work or exclude it while preserving
it. A branch name or clean working directory does not certify the assigned baseline
or absence of another editor. Doctor/status report structure, backend readiness and
repository context; PASS does not prove authentication, capability floors, acceptance
or execution authority. Classify failures before considering a repair in its owning
repository. Resolve matching acceptance requirements by union/OR and routing floors
by maximum rank; missing policy or provenance means HOLD.

## Collect private provider facts

Use the existing [collector](observation-collector.md) with an explicit Issue and,
when known, explicit PR. Replace placeholders before running:

```bash
umask 077
mkdir -p .runtime/diagnostics
./scripts/observe.sh <logical-owner> <issue-number> --pr <known-pr-number> > .runtime/diagnostics/provider.json
```

The mapping is literal JSON from ignored `local/github.json`, or an explicitly
selected `NEXUS_GITHUB_CONFIG` path; do not source it as shell code or print
credentials. Omit `--pr` only when no PR is selected for inspection. Selection is
not proof that the PR belongs to the Issue. Inspect stdout even when the command
exits **2**: every collection is partial, `recovery_input_ready` is false, and successful
requested reads do not attest complete inventories, authenticated freshness or trust.
Exit 1 indicates invocation/configuration failure; preserve the actual diagnostic.

Compare the canonical Issue, PR URL/repository/branch/exact head, current Project
membership and canonical Workflow field. Known PRs prevent blind redispatch.
`scripts/work-items.sh` exposes `issue-read`, `pr-read`, `review-checks-read` and
`association-read`; `scripts/projects.sh read <logical-owner>` reads the configured
Project. Their `--help` and [GitHub adapter](adapters/github.md) define syntax and
pagination limits. A returned Project snapshot is context within its reported limits;
missing membership/status or an empty inventory cannot manufacture a lifecycle state.

Verify association authors, actual decisions, supersession and complete inventories
with the [manual trust procedure](work-associations.md). Missing pointers, multiple
selections, stale heads or unverifiable author/approval scope mean HOLD. Preserve
private evidence locally; publish only separately authorized, reviewed sanitized
records. A collector bundle cannot be fed directly to reconciliation as trusted input.

## Check a plan without changing it

```bash
python3 -B scripts/check-plan.py <ignored-json-plan-path>
```

The [development checker](plan-validation.md) accepts a JSON object, including JSON
stored in a `.yaml` file, under its explicit supported policy/field limits. YAML block
syntax, unsupported layouts, extra fields and unsupported policy revisions produce
NEEDS-WORK (exit 1). Static PASS (exit 0) always has `dispatch_authority: false`.
Read diagnostics with their task/field context; keep the original plan and report
unsupported content. Do not strip real runtime fields or rewrite a plan merely to
make it pass. Use a separately labeled diagnostic example only to demonstrate tool
behavior; it is never the live plan or an approved assignment.

Draft and readiness selectors check different supplied claims as documented by the
checker. No PASS proves object existence, actual capability receipts, independent
execution, writer isolation, live settlement, human authority or current acceptance.

## Compare attempts with project intent

Use the selected [execution adapter's read-only walkthrough](adapters/orca.md#read-only-native-diagnostics)
to inspect exact existing workspaces, known scoped attempts and all required pages.
Record coverage, provenance and unknowns. Match source/Git head and immutable artifacts
to the Issue, PR and reviewed result; keep native identity interpretation inside the
adapter. A complete scoped page is not a global sole-writer proof. Current workers
remain active until their explicit outcome; activity outside observed scope stays unknown.

| Observation | Decision or next evidence |
| --- | --- |
| Existing PR with retained checkout | Inspect that PR/head and related attempts; HOLD blind redispatch. |
| Missing or stale Issue/PR/head/attempt correlation | Preserve records and HOLD affected actions until manually verified. |
| Successful checks on a different PR/head | No transfer of check evidence; observe the selected current head. |
| Card state/link/comment suggests review or completion | Crosscheck provider state and authoritative attempts; context supplies no approval or exit proof. |
| Explicit settled outcome and released session | Record scoped settlement evidence; retain the checkout pending its separate disposition. |
| Timeout, idle, cancellation request, fencing or unknown liveness | HOLD replacement/control/cleanup; investigate through the installed backend contract. |

Respect fresh human pause, cancel, resume, priority, assignment and review decisions.
A pause does not terminate workers; cancellation requests do not prove exit. Retry or
reassignment requires a concrete cause, finite budget, Coordinator decision and proven
prior settlement/editor exit. Read-only observations grant none of those actions.

## Report acceptance and retention separately

Keep local validation, fresh independent validation when required, authoritative
current-head review, native required-check discovery/results, exact human operation
approval and observed merge as separate evidence. Unknown required CI stays `null`
and HOLD. A passing check or review summary cannot establish required-check completeness,
approved current-head review or Done. Implementation Done requires observed authorized
merge and acceptance; non-code work requires an explicit accepted disposition.
Changed candidate, target or approval scope requires renewed evidence.

Finish with the [six-section review summary](review-principles.md#review-self-check-and-final-summary),
exact candidate provenance, actual commands/results, observed coverage, missing facts
and a responsible owner/next trigger for each HOLD. Independent validation uses a
fresh session distinct from the implementer and reports PASS/FAIL/NEEDS-WORK.
No diagnostic PASS grants dispatch, publication, merge or deletion authority.

Record delivered work and workspace disposition separately. Released sessions may
leave useful retained checkouts for review, integration or recovery. Follow
[worktree lifecycle](worktree-lifecycle.md): deletion needs exact separate human
approval, settled activity, preserved data/results and no consumers. Retain/HOLD
when evidence or approval is missing; a merged PR or completed card cannot authorize
cleanup. Record the next review/disposition trigger without an indefinite monitoring
promise.
