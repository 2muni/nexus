# Model selection and effective-setting verification

Use this operator procedure for implementation, planning, review and validation
assignments. Nexus chooses requirements and routing; the execution adapter launches
the assignment and supplies factual observations. This is a human-operated procedure
using existing backend messaging, not an automatic capability checker or approval
engine. Read [routing](routing.md), [review principles](review-principles.md),
[acceptance policy](acceptance-policy.md) and the selected adapter together.

Model choice authorization, task suitability, installed support, account readiness
and actual session settings are separate claims. A user choosing a model authorizes
its use; it does not prove the capability floor. A catalog entry proves advertised
support within its version/scope, not access or execution by this account. Successful
tests or a validator PASS cannot retrospectively certify settings used earlier.

## Select from task requirements

1. Classify the task at its exact owner revision: type, complexity, risk, context
   size, architecture sensitivity, severity, mutation scope and contributing mutable
   inputs. Resolve acceptance provenance before dispatch; missing policy means HOLD.
2. Select the configured task class and apply **all** matching routing rules.
   Profiles combine by maximum rank (`fast < standard < deep < critical`);
   independent-validation requirements combine by logical OR across routing,
   review and acceptance. Documentation or a preferred agent cannot lower a floor.
3. State concrete needs: tools/permissions, usable context for the assigned inputs,
   required output formats/artifacts, and reasoning/judgment needed for contracts,
   debugging, integration or review. Record the abstract effort intent separately
   from any provider effort value.
4. Assess preferred agent/profile and then compatible configured fallback against
   those needs. Justify suitability with versioned provider/installed evidence and
   a concise operational rationale connecting each material need to capability.
   Task-relevant prior observations may support judgment, but name, price, a passed
   test or the highest selectable effort alone cannot establish suitability.
5. Resolve the user-named, authorized local model mapping, or record ownership of
   the configured default when no model is named. Local capability data is inert
   data, never shell code or authority to choose an unauthorized override. Preserve
   unknown model/effort as null. Honor the installed adapter's user-choice rule;
   do not invent a provider ID to satisfy an abstract profile.
6. On the exact execution host inspect installed launcher/backend versions,
   supported model/effort controls and account readiness. Record evidence scope,
   time and limitations. Authentication presence alone does not establish model
   access, quota or the effective reasoning setting. Unavailable preferred agents
   may use a verified compatible authorized fallback, with a recorded reason and
   unchanged floor/validation; otherwise HOLD and ask the Coordinator.
7. Preserve the requested launch receipt, then bind actual observations to the
   resulting logical session and native attempt. Apply the before-work decision
   below, recheck after changes, and include capability evidence in completion.

Profile reasoning labels are policy intent, not provider-independent effort ranks.
`maximum` is not a CLI value; critical means the strongest **verified suitable**
capability for the task. Equivalent effort across models, generations or providers
requires evidence and rationale, never label equality or a universal conversion.
Unsupported requested effort holds until a supported suitable equivalent is verified
and authorized, or a justified default decision meets the rules below. Unknown
equivalence alone is HOLD; do not silently omit the requested effort.

## Decide from evidence

| Evidence state | Before-work decision |
| --- | --- |
| Verified match | Proceed only when actual agent/model/effort in this exact session match the authorized selection, task suitability/floor is established, evidence is fresh and consistent, and all other gates pass. Record `verified`. |
| Inherited unknown | Null/default inheritance is compatible but uncertified. Only low/medium-risk, non-critical work may use the limited decision below; high risk or critical complexity requires HOLD until verified. |
| Known mismatch or below floor | HOLD at **every risk**. A weaker known effort cannot be relabeled unknown; authorization of a model does not waive the floor. Resolve the mismatch through an exact authorized compatible change and fresh observation. |
| Unsupported or unavailable | HOLD the requested choice. Resolve a verified supported equivalent or compatible fallback with the proper authorization; availability alone is insufficient. |
| Stale, conflicting or unbound | HOLD. Resolve conflicting sources and observe the exact current session/attempt again; a previous host, session or setting cannot release work. |

Limited lower-risk inheritance requires a concrete uncertainty statement, why using
the configured default is reasonable for the actual task, what is known about its
suitability, absence of evidence of a mismatch/below-floor capability, and the
policy-required validation plus any necessary additional independent validation.
The Coordinator records `inherit-with-uncertainty` and the bounded decision before
work. This is not certified suitability and cannot excuse a user-requested setting
mismatch, known weaker capability, unsupported-equivalence guess or another HOLD.
Validation requirements never decrease under inheritance or fallback.

## Two-stage start before source mutation

Preparation resolves policy, ownership, baseline, placement, authorization and
available support evidence. Actual settings can require a live session to observe;
launch that session with a **read-only preflight first** specification. Distinguish
permission to start preflight from permission to perform implementation. Preserve
setup policy and inspect any setup effects against the assigned mutation boundaries.
Normal worker-start can deliver a prompt that immediately begins work: merely
comparing receipts later does not establish a before-work safeguard.

The Coordinator includes this first checkpoint in the assigned spec:

> First perform read-only preflight: verify workspace identity, exact head and dirty
> state; inspect actual current agent/model/effort in your own exact session and
> native receipt when available. Use the live preamble's blocking ask to report
> requested versus observed settings, sources, times and session/attempt identity.
> Do not edit source until the Coordinator confirms the routing decision for this
> same attempt. Unknown or mismatched settings mean HOLD; do not change models or
> launch an alternate worker yourself.

The worker reports the initial source as clean or explicitly included/excluded dirty
work, preserving existing edits. The Coordinator independently compares observation,
launch intent, local mapping/rationale and policy floor, then replies through existing
backend ask/reply. Record the exact confirmation reference and scope. For a permitted
inheritance decision the reply must explicitly name its uncertainty and validation.
An unanswered question, a generic permission to implement, or an old confirmation
cannot release this checkpoint. Retrospective comparison is insufficient.

This routing confirmation operates under existing implementation authority; it is
separate from human integration-gate, merge, publication and deletion approval.
Those approvals still require their own exact scopes. There is no new approval engine.
See the [Orca binding](adapters/orca.md#model-and-effort-observation) for concrete
receipt, rendered-screen and messaging mechanics.

## Effective evidence and limits

Capture agent/model **and effort** from a documented current-session diagnostic or
rendered current setting, bound to the exact logical assignment session, host,
backend/agent versions, attempt and observation time. State what each source proves
and what it leaves unknown. Use native opaque references in private adapter evidence;
do not interpret their contents in core policy. Evidence of model alone leaves effort
unknown. Account execution observed in this session is scoped evidence, not a promise
that the same account will have future access or quota.

Requested arguments, a settings file, local `verified: true`, null/default receipts,
a worker's unsupported claim, a fleet model label or `turn_started` alone cannot
certify actual effort. A non-null native effective launch receipt documents launch
resolution; compare it with current-session evidence rather than assuming it proves
continued use. A null native receipt does not invalidate independent positive
current-session model/effort evidence with exact identity and no conflict. Preserve
the null launch fields and explain the source of the positive observation.

For Codex CLI, official [developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
document `/model` as a picker: enter it **without arguments**, choose the visible
authorized model and supported effort, then use `/status` to verify the active model.
Do not invent `/model <id> <effort>` syntax. Inspect the actual rendered selection
before sending any work prompt; pasting a numeric menu choice is not reliable proof
of selection. Only an authorized operator changes settings; the worker checkpoint
does not grant that authority. Observe effort explicitly in the current diagnostic
or rendered model-and-reasoning field; if it is absent, it remains unknown.

Official [developer settings](https://learn.chatgpt.com/docs/developer-settings)
describe `/status` for the current session and `/debug-config` for configuration
layers and requirements. Use layer diagnostics to explain discrepancies, not to
substitute configured intent for an observed setting. The [model guidance](https://learn.chatgpt.com/docs/models)
describes CLI selection and task suitability, warns that effort differs across
generations, and limits availability by account/client/workspace. Reinspect these
version-sensitive sources when needed; they do not certify this assignment's access.

## Recheck and usage limits

Before continuing after resume/reuse, model or effort change, host/account/version
change, scope/risk/context change, conflicting evidence or quota interruption,
reassess requirements and reobserve the exact session. Invalidate stale confirmation
and repeat the blocking checkpoint before further mutation. Preserve prior evidence
and partial edits; do not overwrite history with the latest setting. A reused terminal
does not prove it retained settings or create a fresh independent validator session.

On usage limits, keep the original attempt and partial work; HOLD further mutation.
No automatic downgrade, extra spending, reset, retry or alternate worker is authorized.
The Coordinator needs an exact authorized model/effort change that still meets the
floor, or an explicit justified requirement/scope adjustment consistent with policy.
User approval alone cannot waive a mandatory floor. After any authorized adjustment,
observe the setting in the **same exact session**, recheck suitability/support/account
readiness and record a new checkpoint before continuing. Do not send a work prompt
until the rendered picker selection and effective setting are verified. If replacement
is needed, apply finite recovery rules, preserve identity/evidence and prove prior
settlement and editor exit; unknown liveness never permits a duplicate editor.

At completion record which settings were verified for which work intervals, recheck
current settings, identify unresolved gaps, and attach the exact candidate and required
validation. A later correction or validator PASS cannot certify earlier unknown use.
Capability verification supplies neither acceptance nor lifecycle settlement/exit.

## Private decision record using existing contracts

Keep decisions in ignored `.runtime/runs/<run-id>/` and reports in ignored `reviews/`.
Use existing [plan](../schemas/execution-plan.yaml) `routing.resolution` and
[assignment](../schemas/agent-assignment.yaml) `requested`, `effective`, `evidence`
alongside model profile, abstract effort, reasons and validation. A pending fragment
looks like this; it is illustrative and **not dispatch authority**:

```yaml
routing:
  resolution: {status: pending, model: null, effort: null}
assignment:
  requested: {agent: codex, model: null, effort: null}
  effective: null
  evidence: "pending; see ignored capability-decision.yaml"
```

Update resolution to `verified`, `inherit-with-uncertainty` or `blocked` only with
the corresponding decision; never manufacture effective values. This fragment is
not a complete plan. Do not add verification fields to strict check-plan JSON to
make a sidecar appear supported. The static checker does not validate live evidence
or authorize dispatch; unsupported operational records retain their explicit limits.

Use a compact ignored sidecar for the following extra detail. These are illustrative
record labels for an operator to fill, not new schema fields, an automatically parsed
format, a model mapping or a dispatch mechanism:

| Sidecar detail | Record |
| --- | --- |
| Identity and action | Work/task/assignment IDs, logical `session_ref`, exact base/candidate, opaque native session/attempt/terminal/incarnation refs; action `beforeWork`, `recheck` or `settlement`. |
| Requirements | Classification and policy revision/sources, maximum profile and abstract effort intent, tool/context/output/reasoning needs, required validation and fresh validator identity when known. |
| Authorization and mapping | Exact user choice reference or default owner/source, selected agent/model/effort, compatible fallback reason, versioned suitability evidence and operational rationale. |
| Support and observation | Host, backend/agent versions, account-readiness evidence and limits, requested/effective launch receipt refs, actual observed model/effort, source, timestamps and evidence validity/change triggers. |
| Decision | `verified`, `inherit-with-uncertainty` or `blocked`; concrete reason/unknowns, permitted next action, Coordinator checkpoint reference matching this attempt and observed settings. |

Preserve minimal normalized facts and sanitized references, without credentials or
raw transcript archives. Private sidecars are operational evidence, never an external
hidden sole authority or a competing project record. Externally recoverable decisions
follow existing association/publication rules; do not publish private reports implicitly.
