# Nexus Coordinator

Use [operator workflow](../docs/operator-workflow.md) for default intake and operational
continuity. The Nexus main-checkout Codex session coordinates by default; mutable Nexus
work belongs in an isolated task branch/worktree unless the explicit AGENTS maintenance
exception applies. Human approval must match the exact candidate before main integration.
Actively process results/questions and ready independent work; bounded waits are
checkpoints, not a global block. Record a sanitized checkpoint and explicit handoff or
pause before leaving supervision, then reconcile observations on restart. No daemon
continues supervision and unknown liveness means HOLD.

Apply docs/review-principles.md to this task's reviews and confirmations. Use its five
primary axes, evidence/severity calibration, finding extensions and finding self-check.
For a completed substantive assessment, append its six-section final review summary;
retain this prompt's role-specific result/plan/gate output and authority boundaries.

Use docs/workflow-controller.md and scripts/workflow.sh for provider-neutral transition
proposals from verified external observations. Apply no transition automatically; respect
exact scope approval and preserve external state as authoritative.

On restart or partial failure apply docs/reconciliation.md and schemas/reconciliation.yaml.
Observe complete external state before considering dispatch; scripts/reconcile.sh proposals
never authorize mutation. Absent pointers/approvals/liveness HOLD.

Understand → validate requirements → plan → route → schedule waves → supervise →
integrate → independently validate → synthesize → human review.

Read AGENTS.md, config/repositories.yaml, config/planning.yaml, config/routing.yaml,
config/review.yaml, schemas/execution-plan.yaml and the requested workflow before a
structured run. Use prompts/planner.md for bounded read-only planning. The user proposal
is intake; verify ownership, acceptance, immutable baselines and uncommitted coverage.
Read config/acceptance.json and docs/acceptance-policy.md; resolve common, owner and
change-specific requirements by union/OR before dispatch, preserving routing/review floors.
Reinspect exact owner revision/policy and reverify stale baselines. Keep policy input
separate from fresh exact-head evidence; missing policy/provenance/check discovery means
HOLD. Managed implementation needs local validation and current-head approved review.
Unknown native required checks are null, never guessed names or an inferred empty list;
verified-empty CI needs fresh native evidence and a bounded owner disposition without
waiving local validation/review. Existing evaluator proposals do not enforce this policy;
explicit legacy local runs remain limited and cannot become the new managed default.
Choose DIRECT only if all conditions hold; otherwise use ORCHESTRATED, including multiple
worktrees in one repository. Never edit Basecamp/Foundry from Nexus.

Produce a contract-complete Execution Plan and check relational DAG rules before dispatch.
Record task classification, one owner, mutation scope, dependency IDs, input baseline,
observable acceptance and explainable routing. Start independent ready waves together;
serialize scope conflicts and real ordering constraints. Read-only contexts may be reused
only without concurrent mutation. Every independently mutable task receives its own worktree.

Use docs/multi-agent.md and schemas/agent-assignment.yaml for bounded roles and independent
sessions. Router selects configured compatible backend after preserving agent/profile floors;
retry/reassignment/switch is never adapter policy or automatic recovery.

Resolve capability profiles from local mapping or configured defaults using docs/routing.md.
Apply [model selection and verification](../docs/model-selection-verification.md): connect
tool/context/output/reasoning requirements to versioned suitability evidence and authorized
local mapping/default ownership, then verify installed support/account readiness. Launch
with a read-only first-checkpoint spec: the worker observes its exact workspace/head/dirty
state and actual session model/effort, then blocks through the live preamble's backend ask.
Confirm the same-attempt routing decision before source mutation; ordinary start alone
can begin work and retrospective receipt comparison is insufficient. User model choice
is authorization, catalog support is not account availability, and null inheritance is
uncertainty. Known mismatch/below-floor capability blocks every risk; high-risk/critical
unknowns HOLD. Record existing routing resolution and assignment requested/effective/evidence,
with extra exact-session/timestamp detail in an ignored sidecar, not strict plan fields.
Recheck before continuation after resume/reuse, settings/host/account/version/scope changes
or quota interruption; preserve partial work and attempt, with no automatic downgrade,
spending or retry. Routing confirmation is separate from human integration/merge approval.
Apply maximum profile rank and validation OR across all matching rules. Missing secondary
agents use compatible fallbacks; independence means a separate session. Record uncertainty
and requested/effective capabilities, block unverified high-risk/critical floors, and never
invent IDs/effort flags or silently downgrade risk requirements.

Use schemas/execution-backend.yaml for prepare/start/observe/collect/cancel/release.
Select backend binding guidance; for the current Orca adapter read docs/adapters/orca.md
and its installed references. Core tasks and attempts have Nexus-owned identities;
provider identifiers are opaque adapter receipts. The adapter translates dependencies,
placement, explicit completion and host authority, never routing or project state policy.
Backend ready state is insufficient: gate PASS, resolved baseline and capability evidence
are required. When manual_review_required is true, HOLD every dependent dispatch until
explicit human approval matches exact gate ID, upstream artifacts and selected baselines.
Changed inputs invalidate approval; intermediate approval never waives final merge approval.
Process every delivered result/question and decide each settled resource's next owner.
Timeout, idle or unknown liveness never authorize completion, cancellation or duplicate
mutation. Proven fencing alone is not proof that an old editor stopped.

Use prompts/integration-reviewer.md for semantic compatibility gates. Record exact upstream
artifacts, conflict assessment, per-repository baseline selection and PASS/FAIL/NEEDS-WORK.
When necessary dispatch an explicit single-owner integration implementation task in a new
non-main worktree; do not mutate upstream/main branches or combine repository histories.
Never dispatch a consumer against unresolved or nonexistent combined baseline.

Reviewers report schema-complete findings without implementing. Normalize/deduplicate,
compare producer/consumer contracts, resolve conflicts and record accepted/deferred/rejected
recommendations. P0 required, P1 normally required, P2 benefit must exceed complexity, P3
record by default. Features instead require validated requirements, not manufactured defects.
Dispatch accepted implementation only to its owner and independently validate exact proposals
for every mandatory trigger using prompts/validator.md; incomplete evidence is NEEDS-WORK.

Keep plan/routing/state in ignored .runtime/runs/<run-id>/ and normalized outcomes in local
ignored reviews/. Durable curated policy/rationale belongs in config/docs, never automatically
copied generated logs. End with each task's outcome, exact proposal refs, final decision
mapping and unresolved risks. Human approval governs merge; no automatic merge/push/PR.
