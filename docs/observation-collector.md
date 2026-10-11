# One-shot factual observation collector

`scripts/observe.sh` collects a private JSON bundle through the existing
[Work Item](../schemas/work-item-provider.yaml) and Project read ports. It helps
an operator gather source facts for manual verification without a local workflow
cache, background process or API mutation. Its
[output contract](../schemas/observation-bundle.yaml) is deliberately separate
from workflow and reconciliation input.

Invoke with the owning logical registry key and an explicit positive Issue number:

```bash
./scripts/observe.sh nexus 4 > .runtime/observations.json
# Optional, explicitly selected PR number:
./scripts/observe.sh nexus 4 --pr 7 > .runtime/observations-with-pr.json
```

Create the ignored destination directory yourself if needed. The collector writes
only stdout and a temporary private directory removed at exit. Protect redirected
output permissions, for example with `umask 077`. Bash, Git and jq are required;
the existing provider ports use their configured authenticated CLI. `--help`
requires no provider/backend access. Development tests use Python standard library
and an offline provider mock; no live collection is part of those tests.

The logical repository must exist in `config/repositories.yaml` and have an exact
provider repository mapping in ignored `local/github.json`, or the file specified
by `NEXUS_GITHUB_CONFIG`. This file is literal JSON, never shell code. There is no
embedded owner/repository fallback. The collector projects only the selected
provider repository identity; Project configuration is interpreted by `projects.sh`.
Missing mapping, invalid arguments or missing prerequisites fail with exit 1 before
collection. Missing Project configuration is a failed Project source, while other
available source reads remain useful.

Every invocation reads the canonical Issue, repository Issue and PR inventories,
all Issue association comments, and the configured owning Project. The existing
adapters own canonical URL/number/kind checks, pagination and native identifiers.
Returned records and comments are retained without keyword linkage, filtering for
association markers, or choosing the latest comment. A PR number supplied with
`--pr` requests that exact PR and its current review/check facts; it does not prove
that the PR belongs to the Issue. No PR is selected from comments or list ordering.
No execution receipt or backend inventory is collected in this initial interface;
`backend.attempts` stays null and liveness stays unknown.

Each source names the actual read port operation and its repository/item scope,
collection start/end times, validated read result, completeness/freshness limits
and sanitized diagnostic codes. Raw transport errors and local configuration
values are excluded. Issue content may include private requirements; comments may
contain unauthenticated claims about approvals, associations or validation. Such
claims remain source content and never set trusted flags.

`read_complete: true` means the port succeeded and returned one structurally valid
normalized JSON value, with the collector's applicable cross-read checks passing.
It does not establish complete inventory or authenticated freshness. The canonical
Issue must appear with the same update timestamp in the Issue inventory. A selected
PR must appear with the same head in the PR inventory, and its review/check read
must identify that PR and head. Contradictions are marked inconsistent with withheld
data; failed or malformed sources have false read flags and null data. Reads are
sequential, so this is an observation window rather than an atomic snapshot.
Reobserve after source or head changes; no elapsed-time or timestamp assertion
can certify a stale bundle as current evidence.

The existing normalized list/comment ports do not return explicit pagination
completeness attestations. In particular, the Work Item adapter can normalize an
empty page stream to `[]`; the collector cannot certify absence from that result.
Consequently `inventory_complete` and `freshness_verified` remain null, even after
successful reads. `requested_reads_complete` summarizes requested read success only.
Project `known` distinguishes a received valid snapshot from an unavailable source;
`membership_known` and `member` describe presence/absence in that returned snapshot,
and `status` is the returned canonical field or null. They do not certify a globally
complete inventory. No status is inferred from Issue open/closed state.

Collection always emits `collection_status: "partial"`, `recovery_input_ready: false`
and exits **2**, including when every requested provider read succeeds. This
non-success exit preserves unknown inventory, backend and trust evidence; consume
stdout as partial facts rather than treating exit 2 as an absent output. `--help`
exits 0. Source failures add specific diagnostic codes and false read flags, without
fabricated source references or replacement empty arrays.

The collector cannot authenticate human decisions, resolve semantic associations
or supersession, accept validation, discover required CI, certify capability floors,
prove current-head approved review, schedule, write Project state, dispatch or mark
Done. An approved review summary from the provider is a fact to verify, not accepted
current-head review evidence. One future explicit backend receipt could not prove
complete attempt inventory or another attempt's settlement/liveness. The
[manual association trust procedure](work-associations.md),
[acceptance policy](acceptance-policy.md) and complete external/backend/Git observations
remain prerequisites for constructing trusted
[reconciliation input](reconciliation.md). OPS5's safety verification does not lift
the recovery HOLD caused by missing status, associations, trust, CI or review evidence.

Keep bundles under ignored `.runtime/` or generated `reviews/` with private permissions.
They may contain full normalized Issue/PR/comment source content. Review and sanitize
before any separately authorized publication; never publish credentials, private
reports, host paths or transcript archives. No collector output grants publication,
merge or checkout deletion authority.
