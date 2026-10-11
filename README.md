# Nexus v0.2

Requirements-to-execution control plane for repositories, agents, models, workflows,
reviews, and validation across the development environment.

Nexus turns requirements into bounded Execution Plans, chooses ownership and routing,
supervises workers through the selected backend (currently Orca), checks integration readiness, and prepares results for human
review. Both single-repository work across multiple worktrees and cross-repository
coordination are first-class workflows.

The permanent target is **Nexus owns the workflow; GitHub owns the state; Orca is an
execution backend**. Current scripts still provide Orca-only read-only preflight; GitHub
read/write operations are available through an explicit one-shot provider port; automatic
synchronization is not implemented. Restart reconciliation is an explicit read-only
Coordinator procedure using externally collected snapshots. See the
[migration plan](docs/workflow-migration.md) for staged delivery and compatibility gates.
The [flat operating model](docs/operating-model.md) separates peer responsibilities,
execution-board controls, validation policy and durable recovery evidence.

## Boundaries

| Layer | Responsibility |
| --- | --- |
| Nexus | Requirements, planning, Task DAGs, policy, routing, gates, normalized decisions |
| GitHub | Authoritative Issues, PRs, Projects, CI, reviews, checks and project history |
| Execution backend (currently Orca) | Worktrees, terminals, dispatch, attempt lifecycle, isolation, runtime supervision |
| Basecamp | macOS host provisioning, packages, shell/PATH, developer tools, host prerequisites |
| Foundry | Docker/Compose runtime, bootstrap, containers, project-local environment |

Future repositories are added to `config/repositories.yaml`. No embedded source,
submodules, cross-repository commits, application framework or custom scheduler.

```text
Requirements → Nexus intake / plan / route → Orca repository workers
            → structured completion → integration gate → validation → human decision
```

Each mutable task has one owner, one repository, one isolated worktree and one diff.
Read-only work can reuse a safe context. Each implementation result receives one final
review decision. Reviewers report; a separate task implements accepted findings.

## Shared review standard

[Review principles](docs/review-principles.md) govern all substantive reviews and
confirmations: evidence, minimal change, Orca boundaries, capability floors and integration
correctness come first. Findings require operational impact, the smallest justified
correction and proportional severity; absent evidence is never PASS. AGENTS, prompts and
workflows reference this common standard rather than maintaining separate checklists.

[Repository acceptance policy](docs/acceptance-policy.md) and
[its declarative input](config/acceptance.json) define common and owner-specific floors.
The Coordinator resolves these before dispatch and checks separate exact-head evidence
before acceptance. Native required CI names remain unresolved (`null`) until fresh native
discovery; verified-empty CI needs a bounded owner disposition and never waives local
validation or review. This adds no automatic enforcement or collector.

## Start

Use the Codex Coordinator in Nexus's main checkout as the default intake. Follow the
[operator workflow](docs/operator-workflow.md) for planning, active supervision,
checkpoints and handoff. Mutable Nexus work defaults to an isolated task branch/worktree;
main integration requires human approval of the exact reviewed candidate.

Run from a Nexus Git checkout with Bash and Git. Orca preflight uses the installed Orca CLI;
structured decision/provider tools additionally require jq, and GitHub operations require
installed gh, Python 3 and OpenSSL with configured [GitHub App authentication](docs/github-app-authentication.md).
The development test suite requires Bash, Git, jq, Python 3 and OpenSSL;
its Python tests use the standard library only:

```bash
./scripts/validate.sh
./tests/run.sh                       # offline full suite; no live backend writes
./scripts/doctor.sh                  # all registered repository selectors
./scripts/doctor.sh nexus            # only Nexus
./scripts/status.sh
./scripts/run.sh --objective 'Improve Foundry bootstrap' --repository foundry
./scripts/weekly-review.sh
```

For local validation, run `bash tests/run.sh`. Native GitHub Actions
[CI](.github/workflows/ci.yml) runs the same offline suite on hosted `ubuntu-24.04`
for pull requests (opened, synchronized, reopened or marked ready for review) and
pushes to `main`. The stable job/check name is `Nexus tests`, with a 10-minute
timeout. CI reuses the runner's Bash, Git, jq and Python 3; backend/provider calls
use mocks, so no Orca installation or live account credentials are needed.
The workflow grants only `contents: read` and disables checkout credential
persistence. A local PASS does not establish a native CI result or a required
branch-protection check; acceptance still requires fresh GitHub evidence.

`run.sh` prints preflight results, installed orchestration guidance and a Coordinator
context. It **does not execute the objective**, approve a plan, create a run or start
workers. Give that context to the Coordinator, which reads `AGENTS.md`, the four policies,
the execution-plan contract and selected workflow before acting. `--help` lists options.
`--plan PATH` is an input reference, not semantic validation or permission to execute it.

DIRECT is for one obvious-owner, low-risk task without dependencies or mandatory
independent validation. All other work uses ORCHESTRATED planning. Independent tasks
form parallel waves; dependency edges and explicit integration PASS constrain dispatch.
No automatic merge, push or PR creation. Humans review and approve final changes in Orca.

## Configuration and records

Tracked policy lives in `config/`; capability profiles have no permanent provider model
IDs. Optional `local/repos.env` maps logical repositories to Orca selectors; optional
`local/capabilities.yaml` records host-verified, user-chosen agent/model mappings. Copy
and edit the corresponding examples when needed. These are local data, without secrets;
they are ignored and never executed as shell configuration.

Logical registry keys use lowercase letters/digits/hyphens and exactly two-space
indentation in a block mapping. Inline comments and trailing whitespace on these keys
are allowed; quoted keys, inline repository values and unsupported direct-key indentation
fail explicitly rather than disappearing from diagnostics. A key `my-tools` maps to `MY_TOOLS_REPO_SELECTOR`, default `name:my-tools`.
Only selected repositories are required for feature preflight; Nexus identity is always
checked. Agent availability includes launcher/account readiness, not just PATH presence.

Plans, routing receipts and gate evidence stay under ignored `.runtime/runs/<run-id>/`.
Generated reviews also stay ignored, preserving the user's review-storage preference.
Only curated, explicitly requested durable policy/architecture decisions enter Git.
See [architecture](docs/architecture.md), [routing](docs/routing.md),
[model selection and effective-setting verification](docs/model-selection-verification.md),
[feature execution](workflows/feature-execution.md), [weekly review](workflows/weekly-review.md)
and [plan examples](schemas/examples/). `validate.sh` checks repository structure.
The optional [development plan checker](docs/plan-validation.md) checks JSON-form
plan semantics with explicit supported-policy limits; static PASS grants no dispatch
authority. The Coordinator retains evidence and authorization checks. No external YAML
library is required.

GitHub Work Items: `scripts/work-items.sh --help` uses one-shot App-authenticated `gh` and `jq`,
independent of Orca. Configure ignored `.runtime/github-app.json` from
`local/github-app.json.example` and an external private key; personal credentials are never
a fallback. Writes default to an exact reviewable plan; applying requires a
matching digest and real human publication approval. See [provider binding](docs/adapters/github.md).

Workflow decisions: `scripts/workflow.sh observation.json` proposes status/actions from
verified external facts. It writes no state and invokes no backend/provider. See
[controller policy](docs/workflow-controller.md).

Projects: copy `local/github.json.example` to ignored `local/github.json` and configure
a separate linked Project per repository. `scripts/projects.sh --help` supports canonical
status/priority reads, exact-reviewed Issue registration (`item-add`) and field updates.
Membership changes do not set workflow status or start execution. See [Project setup](docs/github-projects.md).

Observation collection: `scripts/observe.sh --help` gathers a private factual bundle through existing read ports; inventory and trust limits remain explicit. See [collector usage](docs/observation-collector.md).

Operations: [read-only diagnostics](docs/operations-diagnostics.md) covers preflight, static plan checks, provider/backend correlation, acceptance holds and retained checkouts.

Recovery: `scripts/reconcile.sh external-snapshot.json` proposes a decision from complete
verified external state, without reading local runtime records. See [reconciliation](docs/reconciliation.md).
The [durable association contract](docs/work-associations.md) defines sanitized,
human-reviewed Issue comments and manual trust checks; its example is never live evidence.

Backend-independent assignments: [coordination policy](docs/multi-agent.md),
[assignment contract](schemas/agent-assignment.yaml) and [backend registry](config/execution-backends.yaml).
Only current configured capabilities are advertised; unknown replacement support holds work.
