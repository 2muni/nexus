# Development Execution Plan checking

`python3 -B scripts/check-plan.py PLAN` is an optional one-shot **development**
semantic check. It reads local files and prints JSON; it does not run tasks,
execute configuration, contact a provider/backend, or alter plans. Python 3's
standard library is sufficient. The existing `run.sh --plan` reference and
structural `validate.sh` keep their behavior.

Input must be a JSON object, including JSON stored in a `.yaml` file. YAML block
syntax, comments in JSON, duplicate object keys, NaN and Infinity are rejected.
The declarative [Execution Plan contract](../schemas/execution-plan.yaml) remains
owned by Nexus. The checker supports the fields described here; missing,
unsupported or ambiguous fields produce `NEEDS-WORK` diagnostics with `task`,
`field` and `message`. Booleans must be JSON booleans; version must be integer 1.
Exit 0 means static PASS; exit 1 means NEEDS-WORK. Neither result grants authority.

```bash
python3 -B scripts/check-plan.py .runtime/runs/my-run/plan.yaml --draft
python3 -B scripts/check-plan.py .runtime/runs/my-run/plan.yaml --ready-wave W1
python3 -B scripts/check-plan.py .runtime/runs/my-run/plan.yaml --ready-task T1 --execution-requested
```

Without a selector, all tasks must have resolved immutable bases and routing,
and all gate consumers need supplied PASS and approval evidence. This describes
plan consistency, not a claim that every wave can run now. `--draft` allows an
explicit `null` task `base.ref`, pending routing and pending gates for future
work. Initial repository baselines must still be immutable. Draft PASS never
releases consumers. `--ready-task` or `--ready-wave` checks readiness claims only
for the selected tasks while retaining whole-plan structure, policy floors,
DAG and scope checks. Selected tasks require succeeded direct prerequisites;
all ancestral gates must be PASS and appropriately approved. Future task refs
can remain null and future routing can remain pending. Draft and selectors are
mutually exclusive; draft cannot request execution. Task IDs are never rewritten.

## Supported data and evidence claims

Use the contract's required plan/task/routing/wave fields. Baselines use
`{"ref": "<immutable>", "scope": "<inspected scope>", "dirty_state": "<explicit inclusion/exclusion>"}`.
Refs are full lowercase 40/64-digit Git object IDs or `sha256:<64 hex digits>`
for frozen patches. Branch names, abbreviated hashes and placeholder strings
are rejected. The checker verifies syntax and supplied equality, not object
existence, patch materialization or commit mapping. `base.source` is `initial`
or an ancestor task ID. An initial ref matches the owner baseline; a dependency
ref matches its succeeded result artifact or selected gate baseline.

Mutation targets are literal repository-relative paths using letters, digits,
underscores, dots, hyphens and `/`. Parent/child paths overlap. Globs, escapes,
absolute paths and named components are unsupported/ambiguous and return
NEEDS-WORK. Same-wave reads also conflict with overlapping writes. The checker
cannot resolve symlinks, case aliases, generated-file effects or semantic
coupling; the Coordinator still assesses real independence and isolation.

These additional supported task fields make supplied evidence explicit:

- `severity`: P0/P1/P2/P3, when applicable.
- `validation_sessions`: `{"implementation": "<logical session>", "validation": "<different logical session>"}`.
  Required for mandatory or explicitly requested independent validation and
  independent-review/validation tasks. Session names only establish a distinct
  declaration; they do not prove independent execution.
- `result`: `{"outcome": "succeeded", "ref": "<immutable artifact>", "evidence": ["<receipt reference>"]}`,
  or a failed outcome. Required when a consumer claims completed prerequisites,
  a completed dependency baseline, or a PASS gate's exact inputs.
- `upstream_mutations`: distinct mutable dependency ancestors for mutable
  multi-input integration, including writers carried through gates. This
  conservative supported model counts all mutable ancestors as contributing;
  it does not infer which source changes a task actually consumed.

Task classes must match task types: implementation uses an `implementation-*`
class; mechanical uses `implementation-mechanical`; review uses
`independent-review`; other types use the correspondingly named class. Routing
combines the actual supported class default and every matching rule by maximum
profile rank and validation OR. Abstract effort intent must meet the selected
profile's configured reasoning intent. Optional fallbacks stay within the
configured class pair; this cannot establish host/model compatibility.
Verified resolution claims require concrete model/effort values. Selected
high-risk/critical tasks cannot inherit uncertainty. Other selected tasks can
use explicit inherited uncertainty with reasons; no supplied claim is host proof.

Compatibility gates are read-only integration tasks. `gate.upstream` exactly
names direct dependencies and `gate.baselines` covers their repositories plus
repositories of contributing mutable ancestors. A PASS requires nonempty
evidence and succeeded immutable upstream results. Shared consumers of parallel
writers, and consumers of cross-repository mutations, need an ancestral gate
covering those inputs. Consumers must use the selected gate baseline or a
recorded subsequent dependency output; a gate cannot fabricate a combined tree.

For manual review, approval is `approved` with a nonempty evidence reference and
an exact scope object:

```json
{
  "gate_id": "G1",
  "upstream": {"T1": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "baselines": {"nexus": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
}
```

The upstream map contains each gate input's result ref; the baseline map exactly
matches `gate.baselines`. Changed inputs/baselines invalidate the supplied scope.
Pending, rejected, missing or stale approval holds every selected transitive
consumer, including integration preparation. Nonmanual approval must be exactly
`{"status":"not-required","evidence":null,"scope":null}`. A string reference
cannot authenticate a human, durable approval, semantic compatibility or merge
permission. Those remain separate Coordinator/human checks.

`--execution-requested` additionally requires selected tasks' assignments and a
plan `work_item_binding` with `provider: github`, a provider repository string and
canonical `issue_url`. The renamed `work_item` field is unsupported, including
when supplied alongside `work_item_binding`. This minimal checker supports managed GitHub assignment
claims only; explicit legacy local execution is outside its supported scope.
Assignments include every required field in the
[assignment contract](../schemas/agent-assignment.yaml). `work_item_id` equals
that Issue URL, task/owner/agent/profile/effort match routing, and logical IDs
are unique. Reviewer/validator/planner roles remain read-only; write tasks use
implementer. Same-wave writers declare different owner sessions. Validator
assignments bind the exact candidate and a session distinct from each mutable
upstream's supplied implementation assignment. Assignment validation contains
strict `required`, `independent_session` flags and `candidate` (immutable or
null when no validator candidate applies). `evidence` is a nonempty reference
array. `requested` and `effective` each contain `agent`, `model_profile`, `model`,
`effort`, `status` (`verified` or `inherit-with-uncertainty`); effective claims
match routing resolution and cannot lower its profile or validation flags.
The checker cannot prove a real sole writer, live attempt settlement, placement,
backend isolation or an observed effective receipt.

## Explicit policy support and maintenance

The supported policy content is the reviewed snapshot at
`e41e6150db00c9d068b8684f592c4ec593e62968`: the four governance configs,
`config/acceptance.json`, backend registry, Execution Plan and assignment contracts.
The script's `SUPPORTED` allowlist contains SHA256 fingerprints of those files
with blank and full-comment lines removed. PASS includes these fingerprints as
`policy_provenance`. Catalog keys, task-class defaults, profile reasoning/rank,
classification enums and inline routing rules are read from those supported
files; there is no copied model catalog or second routing configuration.

Unsupported content, even a harmless formatting change, returns NEEDS-WORK.
Comments and blank lines can change without updating fingerprints. To support a
new policy revision, review its semantics, update any affected narrow extraction
or checks and regression tests, then update the fingerprints. Merely copying a
new hash is insufficient. This deliberately incurs maintenance when policy
changes: a layout-only reader cannot detect newly added review/planning/acceptance
requirements that it does not implement. Failing closed avoids guessing those
requirements or introducing a general YAML interpreter/policy engine.

The supported acceptance snapshot fixes mandatory independent-validation
triggers and the final human boundary. It does **not** resolve change-specific
acceptance, fresh owner inspection, native CI discovery, current-head review,
local validation, actual capabilities, authorization or recovery evidence.
Unknown required CI remains null/HOLD under
[acceptance policy](acceptance-policy.md); static PASS never supplies an empty
check set. All results include `dispatch_authority: false`. The Coordinator
must still inspect every missing fact and preserve final merge/publication and
checkout deletion boundaries. Tracked schema examples are YAML draft references,
not ready inputs; this tool does not rewrite or certify them.

Run `bash tests/run.sh` for the offline development suite. The semantic tests
exercise valid single/multi-repository, serial/parallel plans and adversarial
ownership, dependency, routing, independent-session, gate and input cases.
