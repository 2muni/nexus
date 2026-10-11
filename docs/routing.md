# Planning and routing

Read `config/planning.yaml`, `config/routing.yaml`, `config/review.yaml` and the plan
contract together. Task classification covers type, complexity, risk, context size,
parallelizability, repository, dependencies and mutation scope. Testing/documentation/
integration tasks can write only when the plan explicitly declares that scope.

## Select a task class

| Task characteristics | Class |
| --- | --- |
| Design/contract decisions | architecture |
| Implementation with high/critical complexity or architecture sensitivity | implementation-complex |
| Ordinary implementation | implementation-standard |
| Proven mechanical, low-risk edits | implementation-mechanical |
| Debugging / testing / documentation / research | corresponding class |
| Compatibility gate or candidate combination | integration |
| Independent review / final validation | independent-review / validation |

Large context or high complexity raises the capability floor to deep. Risk, critical
complexity and architecture sensitivity apply additional overrides. Review/validation
sessions themselves do not recursively require another validator solely because they
are independent: mandatory validation applies to the candidate changes and design outputs.
The multi-upstream rule targets **mutable integration changes**; a read-only compatibility
gate still inspects evidence and blocks consumers until PASS. Count distinct mutable result
inputs contributing to a candidate, including inputs carried through prerequisite gates;
counting only immediate dependencies would incorrectly hide T2/T3 behind G1. A mutable
integration task declares these input IDs as `upstream_mutations` in its plan.

## Resolve policy to capabilities

1. Pick a task class from the configurable catalog, based on the task's characteristics.
2. Apply every matching override. Profile rank is `fast < standard < deep < critical`;
   select the highest floor. Independent-validation flags combine with logical OR.
3. State needed tools, usable context, output contracts and reasoning/judgment, then
   assess preferred agent and compatible fallback against those requirements.
4. Resolve user-authorized local mapping/default ownership; verify installed support
   and account readiness on the actual host, preserving evidence scope and uncertainty.
5. Record requested launch settings, observe actual model/effort in the exact session,
   and complete the blocking Coordinator checkpoint before source mutation. Record
   effective evidence, suitability rationale, fallback reason and validation.

Follow [model selection and verification](model-selection-verification.md) for the
full sequence, two-stage start, evidence states and rechecks. Suitability needs versioned
evidence connected to task needs; model naming, price, user authorization and successful
tests do not certify capability. Provider effort labels have no universal equivalence.

Fast means low reasoning/latency priority; standard is balanced; deep favors high reasoning;
critical requires the strongest verified suitable capability. Profile reasoning labels are
policy intents. `maximum` is **not** a backend CLI effort flag. Never send abstract profile names
as model IDs. A mechanical task cannot lower a critical/high-risk override.

Optional agent absence alone never fails a workflow. Fallback must preserve the required
capability floor; if no compatible capability is verified, hold the task and report the
missing mapping. A separate Codex session can provide independent review when Antigravity
is unavailable; independence is about session and evidence, not vendor diversity.

`local/capabilities.yaml.example` documents local data with null model/effort and unverified
status. A user-maintained chosen-model mapping supplies authorization for that model;
verify support before launch. Null means inherit, not a quality certification. Unmapped
low/medium-risk, non-critical work can inherit defaults only with a concrete bounded
Coordinator decision recording uncertainty, operational reason and required validation;
this never certifies suitability. Unknown floors for high-risk/critical work hold dispatch.
Known setting mismatches or below-floor capability block work at every risk. Unsupported
effort holds until a suitable supported equivalent is verified/authorized or a justified
default decision preserves policy; unknown equivalence alone cannot release work.
Unavailable preferred choices require a compatible authorized fallback, not merely any
available model. Stale/conflicting evidence holds pending exact-session reobservation.

## Backend selection and assignment

Use config/execution-backends.yaml and schemas/agent-assignment.yaml after task/agent
classification. The Router chooses the backend; adapters execute the exact assignment
and report effective capabilities. Native state/IDs never choose policy or task priority.
Only Orca is currently configured; unavailable capability/backend holds work rather than
inventing LocalGit/remote fallbacks. For its installed operations and launch restrictions,
read docs/adapters/orca.md and current version guidance.

A reviewer/validator/planner has read-only authority. Independent validation has a separate
logical session and exact candidate; agent family diversity is preferred, not mandatory.
Each concurrent mutable assignment gets one owning repository and its own isolated worktree.
Split separately reviewable changes into linked Issues when parallel isolation benefits the
work; never share an editor workspace merely to preserve default Issue/worktree cardinality.
After parallel results require exact compatibility gates and integrated validation before
consumers, including conditional intermediate human approval.

Retry/reassignment/backend replacement is a finite explicit Coordinator decision after
settlement and proven editor exit. Fencing without termination does not permit conflicting
mutation. Preserve Work Item/task identity, immutable artifacts, floors and validation;
reverify assignment/placement on the new host. Human overrides cannot silently waive these
safety requirements. See docs/multi-agent.md for scenario evidence and limits.

## Decision record

For each non-trivial task, `.runtime/runs/<run-id>/routing.yaml` records concise operational
reasons (for example architecture-sensitive, large context, required contract review),
requested/effective configuration, verification source and fallback. No private reasoning
or raw transcripts. Plans name requirements/findings, acceptance checks, dependency waves,
gates and validation tasks. Transient records do not become Git history automatically.
Use existing `routing.resolution` and assignment `requested`/`effective`/`evidence`;
keep extra host/session/timestamp and checkpoint details in an ignored sidecar as described
in the procedure, without adding unsupported fields to strict check-plan JSON. Reobserve
after reuse, resume, setting/host/account/version/scope changes or quota interruption.
