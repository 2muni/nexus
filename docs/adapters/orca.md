# Orca execution adapter

This document is the current backend binding for `schemas/execution-backend.yaml`.
Only this adapter guidance interprets native Run/Task/Dispatch IDs, states, workspace
selectors and commands. Core work/task/execution identities remain Nexus-owned; record
native identifiers as opaque metadata and retain the exact server/caller context.
No new agent subprocess framework is introduced: the Coordinator invokes installed Orca
primitives under this binding. Shell tools expose only read-only preflight/status.

## Version and capabilities

Resolve the executable once using the installed skill stub. Inspect `status --json` and
`skills get orchestration`. Load placement, coordinator-loop, messaging-and-gates and
recovery-and-cleanup references at their action gates. Examples below use `orca` only
as the selected executable; replace it if the session selected another binary.
Commands were checked against installed 1.4.222; reverify on a different host/version.
Do not pass a model unless the user named one; abstract capability intent is not a CLI
argument. Verify requested/effective receipts and preserve user setup policy.

## Operation binding

| Port operation | Orca mechanics and evidence |
| --- | --- |
| prepare | Inspect runtime, version guidance, owning repository identity, exact Git baseline and placement. Bind a native run only for authorized execution; record its mapping outside core task identity. Check all Nexus prerequisites first. |
| start | Create the native task from the bounded spec; map dependency IDs in adapter metadata. Initial start uses `orchestration worker-start --task <native-task> --worktree <verified-placement> --agent <assigned-agent> --run <native-run> --json`. Omit `--retry-request` for an initial request. Immutable base, mutation scope, assignment and identity must be carried in spec/placement; inspect returned identities. |
| observe | Use scoped paginated `worker-list --run <native-run> --include-remote --json`, then exact `worker-show --dispatch <native-attempt> --json` as warranted by installed recovery guidance. Normalize proven live/exited versus unknown; terminal liveness is not agent liveness. |
| collect | Consume explicit completion delivery for the active native attempt; inspect result artifacts, provenance, tests and capability receipts. `worker-read --dispatch <native-attempt>` may supply diagnostic evidence, never invented success. Completion is not Nexus acceptance. |
| cancel | Use the installed recovery contract and exact authorized attempt. `worker-stop` requires positive authority/evidence; `worker-abandon` fences orchestration without killing resources. Unknown liveness authorizes neither. Record requested/confirmed/unknown separately. |
| release | After accepted settlement use exact `worker-release --dispatch <native-attempt> --json`, proven immediate reuse, or user-requested retention. Observe ambiguous cleanup through installed recovery instructions. Never substitute terminal close. |
| delete checkout | Separate human-approved operation under `docs/worktree-lifecycle.md`; no port release calls removal. |

A native task/worker in ready/running/completed state does not choose project status or
routing. Normalize observations conservatively: accepted explicit succeeded/failed outcome
maps to that outcome; proven running agent maps to running; proven question wait maps to
awaiting_input; proven exit without result and missing/unrecognized fields map to unknown.
A cancellation receipt must distinguish fencing from confirmed process termination.
Never allow a normalized cancelled state to imply safe resource reuse without host proof.

## Asynchronous failures and recovery

Start receipts can name a dispatch and residual resources even on failure. Preserve them.
When response delivery is lost, inspect `orchestration request-show --request <original-request-uuid> --json`
under the same caller identity. Only when the installed recovery contract permits replay,
append `--retry-request <original-request-uuid>` to the original command, using the exact
UUID Orca returned for that request. A Nexus operation/task/run ID or a newly generated
UUID is not a replay token. A preserved 1.4.222 preflight rejection of an invalid
retry token instructed the caller to use the exact returned UUID or omit the flag
for a new request. This observation does not test every possible UUID; do not
repeatedly start workers to test it.
Read completed receipts instead of replaying; an absent receipt is not proof no worker exists.

Retry of a proven failed/stopped attempt uses the same native task and explicit placement
with `--retry-of <native-attempt>`. Nexus decides finite budget, agent/capability and gates.
Unverifiable host or attempt state holds dispatch and backend switching. An abandon fence
alone does not prove a previous editor stopped and cannot authorize conflicting mutation.

## Current shell compatibility

`scripts/execution-backend.sh` selects the read-only backend port; `run.sh`, `doctor.sh`
and `status.sh` call it. The adapter owns all direct CLI calls and native diagnostic output.
Legacy helper names remain lazy shims for existing callers. Only Orca is configured; an
unsupported backend fails without fallback. Future adapters implement the same preflight
port plus the Coordinator lifecycle contract. No dummy production backend is added.

`nexus_backend_observation execution-id external-attempt-id observed-at receipt.json`
normalizes inspected worker-show projection receipts without CLI calls. `jq` is required
only for this JSON operation; legacy preflight still needs only Bash/Git/Orca. It refuses
to treat start readiness, process exit, missing durable evidence or another attempt as a
successful result. It deliberately leaves wait/cancellation detail unknown unless proven.

`tests/execution-contract.sh` checks asynchronous start versus result, live/no-result,
explicit durable success/failure, exit without result, stale identity, contact loss,
unsupported versions and backend failure. Prepare/start/cancel/release are Coordinator
operation walkthroughs below, not executable mutators or claims of live remote testing:

| Walkthrough | Required conclusion |
| --- | --- |
| prepare finds unresolved baseline or stale gate approval | HOLD start; preparation never creates a worker |
| start times out with residual native attempt | Preserve receipt; observe same attempt/operation, never second start |
| collect sees another attempt or idle/exit without outcome | NEEDS-WORK; no acceptance or release |
| cancel requested while host unreachable | unknown; retain resources, no stop/abandon or replacement |
| cancel returns fencing with remaining live editor | no conflicting mutation or checkout reuse |
| release lacks accepted explicit settlement | HOLD; no terminal or checkout removal |
| settled release returns ambiguous cleanup | observe exact recovery receipt; no guessed terminal close |
| terminal released after accepted result | keep checkout until separately authorized deletion eligibility |

Independent validation reviews these walkthroughs against the port contract. Live
mutation/cancellation is intentionally not exercised against user workers.

## Read-only native diagnostics

After resolving the executable and loading the version-matched guides above, use exact
workspace selectors and the known Run. Replace every angle-bracket placeholder with
an inspected value; these commands observe existing resources:

```text
orca worktree show --worktree path:<absolute-workspace-path> --json
orca orchestration run-show --id <native-run-id> --json
orca orchestration task-list --run <native-run-id> --brief --json
orca orchestration worker-list --run <native-run-id> --include-remote --json
orca orchestration worker-list --run <native-run-id> --include-remote --cursor <page-nextCursor> --json
orca orchestration worker-show --dispatch <native-dispatch-id> --json
```

For `worker-list`, retain `scope` and every page until `page.hasMore` is false;
copy `page.nextCursor` unchanged. Completeness is limited to that Run and covered
hosts, never all work on a machine. `task-list --brief` truncates specs and is an
index, not the complete task authority. Inspect exact Dispatches from the inventory.
Fleet `projection.liveness` reports agent evidence; `worker-show`'s
`observation.status` describes the PTY. Apply the installed recovery guide's
source-specific precedence when they differ; `unverifiable` remains unknown and
permits no duplicate editor, stop, release or cleanup. Read-only diagnostics do not
authorize a suggested `nextAction` mutation. Reobserve after state or identity changes.

`worktree show` exposes workspace `head`, `branch`, identity/host, `workspaceStatus`,
`linkedIssue`, `linkedPR` and `comment`. A useful comment can point to an existing
PR, review hold and retention reason, while a missing PR link or empty comment can
leave context incomplete. Crosscheck with canonical provider and Git observations;
metadata cannot prove association, approval, sole ownership, process exit or completion.
An `in-review` or `in-progress` workspace can remain after attempts are succeeded,
released and observed exited. Released sessions and retained checkouts are separate.

CLI metadata inspection does not test card rendering, navigation, drag/drop, menus
or control behavior; visual interaction remains untested. Native columns and links
are execution context, never authority to mirror or overwrite GitHub Project state.
Use the [operator diagnostics procedure](../operations-diagnostics.md) for the
cross-system comparison and HOLD decisions. Preserve private scoped receipts rather
than copying paths, native IDs or transcripts into public guidance.

## Assignment capability limits

Installed CLI observations do not constitute a general agent/model availability catalog.
Verify launcher/account readiness, user-authorized model choice and observed launch receipts;
PATH presence and requested args alone cannot certify the required floor. On inspected
1.4.222, OpenCode model overrides require existing-worktree placement and do not support
reasoning-effort overrides. Never weaken isolated mutable placement to obtain an override;
use verified inheritance or a compatible agent. Always recheck installed guidance.

## Model and effort observation

Apply the [Nexus selection procedure](../model-selection-verification.md); this binding
supplies Orca mechanics, not suitability policy. On inspected Orca 1.4.222, load
`skills get orchestration --reference references/coordinator-loop.md` and inspect
`orchestration worker-start --help`. Pass `--model` only for a user-named choice;
`--effort` requires that model's supported setting and `--model`. Neither override
combines with `--terminal`. Omitted/null values preserve configured inheritance but
do not certify the actual model or effort. Recheck host/version support before use.

Start with a spec that requires read-only preflight and a blocking Coordinator ask
before source mutation. Preserve `launch.requested` and `launch.effective` from the
start receipt/worker-show when present. A ready/input-accepted/`turn_started` receipt
proves start, not effective capability or permission to bypass this checkpoint.
For a terminal-backed worker, inspect the exact returned terminal on its owning host:

```text
orca orchestration worker-show --dispatch <native-dispatch-id> --json
orca terminal show --terminal <returned-terminal-handle> --json
orca terminal read --terminal <returned-terminal-handle> --screen --json
```

Require `source: screen` for rendered model/effort evidence; accumulated stream,
`screen-unavailable`, absent source or a stale preview cannot verify a current rendered
setting. Bind observations to host/runtime, versions, Dispatch, terminal incarnation,
logical assignment session and time. Preserve opaque native references privately.
Fleet model alone leaves effort unknown. If the worker has no terminal, use its
documented current-session evidence surface; do not apply terminal commands to an
unsupported handle or treat transcript claims as effective proof. Missing evidence
uses the procedure's unknown/HOLD rules.

The worker uses the exact live preamble's `orchestration ask --from <worker-handle>`
to report requested/observed model and effort, sources, identity/time, exact Git head
and clean or included/excluded dirty source. Await a same-attempt Coordinator reply
before editing. Use the installed ask/reply contract; after an ask timeout resume its
returned message ID, never create a duplicate question. Coordinator routing confirmation
does not supply human integration/merge/publication/deletion approval. Existing backend
messaging carries the checkpoint; no automatic enforcement is added.

For proven same-terminal reuse, reobserve settings before work; `--terminal` cannot
apply model/effort overrides. A previous launch receipt cannot certify retained settings
or validator independence. Resume, host/account/version/scope or setting changes and
quota interruptions invalidate stale confirmation. Preserve the attempt/partial edits
and HOLD; any authorized compatible setting change needs fresh same-session observation
and checkpoint. Do not auto-downgrade, spend, reset, retry, stop or start another worker.
When an operator is authorized to change Codex settings, use the documented `/model`
picker without arguments, verify the rendered selection and active model/effort before
any work prompt; numeric paste alone is not selection proof. See the procedure's
official `/status` and `/debug-config` sources and evidence limits.
