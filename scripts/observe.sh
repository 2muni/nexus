#!/usr/bin/env bash
# One-shot factual collection through existing read ports; never workflow input.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} == --help ]]; then
    cat <<'USAGE'
Usage: scripts/observe.sh LOGICAL-REPOSITORY ISSUE-NUMBER [--pr PR-NUMBER]
Reads the configured owning repository, canonical Issue, repository Issue/PR lists,
all Issue comments and canonical Project via existing read ports. Optional PR and
review/check reads require explicit --pr selection; selection is not an association.
Mapping: local/github.json (or NEXUS_GITHUB_CONFIG), literal JSON, never executed.
Private factual JSON bundle on stdout; no cache, backend calls or API mutations.
Exit 0: help only; 1: invalid invocation/configuration; 2: partial factual bundle.
Current ports cannot attest to complete inventories/trust; recovery always remains HOLD.
USAGE
    exit 0
fi
[[ $# == 2 || $# == 4 ]] || nexus_fail 'Expected logical repository and positive Issue number; optional --pr NUMBER.'
logical=$1; issue_number=$2; selected_pr=''
[[ "$issue_number" =~ ^[1-9][0-9]*$ ]] || nexus_fail 'Positive Issue number required.'
if [[ $# == 4 ]]; then
    [[ "$3" == --pr && "$4" =~ ^[1-9][0-9]*$ ]] || nexus_fail 'Expected --pr and positive PR number.'
    selected_pr=$4
fi
command -v jq >/dev/null 2>&1 || nexus_fail 'jq required for observations.'
nexus_root
NEXUS_REPOSITORIES=$(nexus_repository_keys)
nexus_repository_known "$logical" || nexus_fail 'Unknown owning logical repository.'
config=${NEXUS_GITHUB_CONFIG:-"$NEXUS_ROOT/local/github.json"}
[[ -f "$config" && -r "$config" ]] || nexus_fail 'Readable local provider mapping required.'
# Project configuration remains exclusively interpreted by the Project port.
repository=$(jq -ers --arg logical "$logical" '
  if length == 1 and .[0].version == 1 and (.[0].repositories|type == "object") and
    (.[0].repositories[$logical].repository|type == "string" and length>0)
  then .[0].repositories[$logical].repository else error("Owning provider mapping missing or malformed") end
' "$config" 2>/dev/null) || nexus_fail 'Owning provider mapping missing or malformed.'
umask 077
scratch=$(mktemp -d "${TMPDIR:-/tmp}/nexus-observe.XXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '[]\n' > "$scratch/sources.json"

# Validate one complete normalized JSON value, not a stream or a truncated value.
# Adapter identity checks own canonical URL syntax and provider-native semantics.
collect() {
    local name=$1 operation=$2 number=$3 port=$4 shape=$5 before after state diagnostic
    before=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    state=unavailable; diagnostic=read_failed
    if [[ "$port" == projects ]]; then
        if bash "$NEXUS_ROOT/scripts/projects.sh" read "$logical" > "$scratch/raw" 2>/dev/null; then state=returned; fi
    else
        if bash "$NEXUS_ROOT/scripts/work-items.sh" "$operation" "$repository" ${number:+"$number"} > "$scratch/raw" 2>/dev/null; then state=returned; fi
    fi
    after=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if [[ "$state" == returned ]]; then
        state=invalid; diagnostic=malformed_or_mismatched_response
        if jq -es --arg repo "$repository" --arg logical "$logical" --arg number "$number" --arg shape "$shape" '
          def text: type == "string" and length>0;
          def timestamp: type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$");
          def item($kind): type == "object" and .repository == $repo and .kind == $kind and
            (.number|type == "number" and floor == . and .>0) and (.id|text) and .id == .url and
            (.provider|text) and (.title|type == "string") and (.body|type == "string") and
            (.record_state == "open" or .record_state == "closed" or ($kind == "pull-request" and .record_state == "merged")) and
            (.updated_at|timestamp);
          length == 1 and (.[0] |
            if $shape == "issue" then item("issue") and (.number|tostring) == $number
            elif $shape == "pr" then item("pull-request") and (.number|tostring) == $number and (.metadata.head_revision|text)
            elif $shape == "issues" or $shape == "prs" then type == "array" and
              all(.[]; item(if $shape == "issues" then "issue" else "pull-request" end)) and
              ([.[].id]|length == (unique|length))
            elif $shape == "comments" then type == "array" and all(.[];
              (.id|text) and (.body|type == "string") and (.author|text) and (.updated_at|timestamp)) and
              ([.[].id]|length == (unique|length))
            elif $shape == "project" then type == "object" and .repository == $logical and
              (.project_url|text) and (.work_items|type == "array") and
              all(.work_items[]; (.work_item_id|text) and (.fields|type == "object")) and
              ([.work_items[].work_item_id]|length == (unique|length))
            elif $shape == "checks" then type == "object" and (.url|text) and (.head_revision|text) and
              (.merged|type == "boolean") and (.draft|type == "boolean") and
              (.review_state as $state | ["approved","changes-requested","pending","unknown"]|index($state)) != null and
              (.checks|type == "array") and all(.checks[]; (.name|text) and
                (.state as $state | ["pass","fail","pending","unknown"]|index($state)) != null)
            else false end)
        ' "$scratch/raw" >/dev/null 2>&1; then
            state=observed; diagnostic=inventory_and_freshness_not_attested
            jq -s '.[0]' "$scratch/raw" > "$scratch/data.json"
        fi
    fi
    [[ "$state" == observed ]] || printf 'null\n' > "$scratch/data.json"
    jq --arg name "$name" --arg operation "$operation" --arg port "$port" --arg repository "$repository" \
       --arg logical "$logical" --arg number "$number" --arg before "$before" --arg after "$after" \
       --arg state "$state" --arg diagnostic "$diagnostic" --slurpfile data "$scratch/data.json" '
       . + [{name:$name,source:{port:$port,operation:$operation,repository:(if $port == "projects" then $logical else $repository end),
          item_number:(if $number == "" then null else $number end)},
          started_at:$before,observed_at:$after,status:$state,read_complete:($state == "observed"),
          inventory_complete:null,freshness_verified:null,diagnostics:[$diagnostic],data:$data[0]}]
    ' "$scratch/sources.json" > "$scratch/next.json"
    mv "$scratch/next.json" "$scratch/sources.json"
}
collect issue issue-read "$issue_number" work-items issue
collect issues issue-list '' work-items issues
collect pull_requests pr-list '' work-items prs
collect comments association-read "$issue_number" work-items comments
collect project read '' projects project
if [[ -n "$selected_pr" ]]; then
    collect selected_pr pr-read "$selected_pr" work-items pr
    collect review_checks review-checks-read "$selected_pr" work-items checks
fi
# Cross-read contradictions are evidence of an inconsistent observation window.
# Preserve only validated facts, withhold contradicted data rather than choosing a winner.
jq '
  def source($n): [.[]|select(.name == $n)][0];
  . as $s | source("issue").data as $issue | source("issues").data as $issues |
  source("selected_pr").data as $pr | source("pull_requests").data as $prs |
  source("review_checks").data as $checks |
  map(if (.name == "issues" and $issue != null and $issues != null and
           ([$issues[]|select(.id == $issue.id and .updated_at == $issue.updated_at)]|length) != 1) or
         (.name == "selected_pr" and $pr != null and $prs != null and
           ([$prs[]|select(.id == $pr.id and .metadata.head_revision == $pr.metadata.head_revision)]|length) != 1) or
         (.name == "review_checks" and ($pr == null or ($checks != null and
           ($checks.url != $pr.url or $checks.head_revision != $pr.metadata.head_revision))))
      then .status="inconsistent" | .read_complete=false | .data=null |
           .diagnostics=["cross_read_identity_or_revision_mismatch"] else . end)
' "$scratch/sources.json" > "$scratch/next.json"
mv "$scratch/next.json" "$scratch/sources.json"
jq --arg logical "$logical" --arg repository "$repository" --arg requested_issue "$issue_number" \
   --arg pr "$selected_pr" --arg started "$started_at" --arg finished "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  def source($n): [.[]|select(.name == $n)][0];
  . as $sources | (source("issue").data) as $issue | (source("project").data) as $project |
  {version:1,kind:"nexus-observation-bundle",started_at:$started,observed_at:$finished,
   owner:{repository:$logical,provider_repository:$repository,issue_number:$requested_issue,
     work_item_id:($issue.id // null),mapping_source:"configured-local-provider-mapping"},
   selection:{requested_pr_number:(if $pr == "" then null else $pr end),association_verified:null},
   sources:$sources,requested_reads_complete:all(.[]; .read_complete),
   project:{known:($project != null),membership_known:(if $project == null or $issue == null then false else true end),
     member:(if $project == null or $issue == null then null else any($project.work_items[]; .work_item_id == $issue.id) end),
     status:(if $project == null or $issue == null then null else first($project.work_items[]|select(.work_item_id == $issue.id)|.fields.status) // null end)},
   backend:{observed:false,inventory_complete:null,liveness:"unknown",attempts:null},
   trust:{associations_verified:null,human_decisions_verified:null,validation_accepted:null,
     capabilities_verified:null,required_ci:null,current_head_review_verified:null},
   collection_status:"partial",recovery_input_ready:false,
   diagnostics:["inventory_completeness_unverified","backend_inventory_and_liveness_unknown","manual_trust_and_acceptance_required"]}
' "$scratch/sources.json"
exit 2
