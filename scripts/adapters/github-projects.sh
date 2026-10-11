# ProjectV2 binding; API IDs, option names and pagination stay adapter-owned.
nexus_github_project_snapshot() {
    local mapping=$1 owner kind number project fields items query
    owner=$(jq -r .project.owner <<< "$mapping"); kind=$(jq -r .project.owner_kind <<< "$mapping"); number=$(jq -r .project.number <<< "$mapping")
    [[ "$kind" == user || "$kind" == organization ]] || nexus_fail 'Unsupported Project owner type.'
    query="query(\$owner:String!,\$number:Int!){owner:$kind(login:\$owner){projectV2(number:\$number){id number title url repositories(first:100){nodes{nameWithOwner} pageInfo{hasNextPage}}}}}"
    project=$(nexus_github_api graphql -f query="$query" -f owner="$owner" -F number="$number" |
      jq -ec 'if (.errors|length)>0 or .data.owner.projectV2.id == null then error("Project unavailable") else .data.owner.projectV2 end')
    jq -e --argjson number "$number" '(.id|type == "string" and length>0) and .number == $number and (.url|type == "string" and length>0)' <<< "$project" >/dev/null || nexus_fail 'Project identity missing or mismatched.'
    jq -e --arg repo "$(jq -r .repository <<< "$mapping")" '.repositories.pageInfo.hasNextPage == false and any(.repositories.nodes[]; .nameWithOwner == $repo)' <<< "$project" >/dev/null || nexus_fail 'Project not linked to exact owning repository or linkage inventory incomplete.'
    fields=$(nexus_github_api graphql -f query='query($id:ID!,$endCursor:String){node(id:$id){... on ProjectV2{fields(first:100,after:$endCursor){nodes{... on ProjectV2FieldCommon{id name} ... on ProjectV2SingleSelectField{options{id name}}} pageInfo{hasNextPage endCursor}}}}}' \
      -f id="$(jq -r .id <<< "$project")" --paginate --slurp |
      jq -ec 'if length==0 or any(.[]; (.errors|length)>0 or .data.node.fields == null) or
        .[-1].data.node.fields.pageInfo.hasNextPage != false or
        any(.[0:-1][]; .data.node.fields.pageInfo.hasNextPage != true or (.data.node.fields.pageInfo.endCursor|type != "string" or length==0)) then error("Field query incomplete") else [.[].data.node.fields.nodes[]] end')
    # Require an unambiguous single-select field and unique option for every mapped value.
    jq -e --argjson fields "$fields" '.project.fields | to_entries | all(.[];
      .value as $m | [$fields[]|select(.name == $m.name)] as $f |
      ($f|length) == 1 and ($f[0].options|type == "array") and
      ($m.options|type == "object" and length>0) and
      ($m.options|[.[]]|unique|length) == ($m.options|length) and
      ($m.options|to_entries|all(.[]; .value as $name | [$f[0].options[]|select(.name == $name)]|length == 1)))' <<< "$mapping" >/dev/null || nexus_fail 'Missing, ambiguous or non-single-select Project fields/options.'
    items=$(nexus_github_api graphql -f query='query($id:ID!,$endCursor:String){node(id:$id){... on ProjectV2{items(first:100,after:$endCursor){nodes{id content{... on Issue{id url repository{nameWithOwner}}} fieldValues(first:100){nodes{... on ProjectV2ItemFieldSingleSelectValue{name optionId field{... on ProjectV2FieldCommon{id name}}}} pageInfo{hasNextPage}}} pageInfo{hasNextPage endCursor}}}}}' \
      -f id="$(jq -r .id <<< "$project")" --paginate --slurp |
      jq -ec 'if length==0 or any(.[]; (.errors|length)>0 or .data.node.items == null) or
        .[-1].data.node.items.pageInfo.hasNextPage != false or
        any(.[0:-1][]; .data.node.items.pageInfo.hasNextPage != true or (.data.node.items.pageInfo.endCursor|type != "string" or length==0)) then error("Item query incomplete") else [.[].data.node.items.nodes[]] end')
    jq -e 'all(.[]; .fieldValues.pageInfo.hasNextPage == false)' <<< "$items" >/dev/null || nexus_fail 'Item field inventory incomplete; HOLD instead of truncating.'
    jq -cn --argjson project "$project" --argjson fields "$fields" --argjson items "$items" --argjson mapping "$mapping" '{project:$project,fields:$fields,items:$items,mapping:$mapping}'
}
# Membership is independent of workflow/priority. The plan binds immutable provider
# identities, not whether the item happened to exist at preparation time.
nexus_github_project_membership() {
    local logical=$1 mapping=$2 snapshot=$3 request=$4 apply=$5 approved=$6 approval=$7
    local repo url number issue content project matches plan oid result='' received valid=false
    [[ -f "$request" && -r "$request" ]] || nexus_fail 'Item add requires request JSON.'
    jq -e 'type == "object" and keys == ["issue_url"] and (.issue_url|type == "string")' "$request" >/dev/null || nexus_fail 'Item add accepts only issue_url; fields need separate plans.'
    repo=$(jq -r .repository <<< "$mapping"); url=$(jq -r .issue_url "$request")
    jq -e --arg prefix "https://github.com/$repo/issues/" '.issue_url | startswith($prefix) and (ltrimstr($prefix)|test("^[1-9][0-9]*$"))' "$request" >/dev/null || nexus_fail 'Expected canonical Issue URL in the exact owning repository.'
    number=${url##*/}
    issue=$(nexus_github_api "repos/$repo/issues/$number" --method GET)
    jq -e --arg url "$url" --arg number "$number" '(has("pull_request")|not) and .html_url == $url and (.number|type == "number" and floor == . and .>0) and (.number|tostring) == $number and (.node_id|type == "string" and length>0)' <<< "$issue" >/dev/null || nexus_fail 'Issue identity missing, changed or is a PR; reobserve.'
    content=$(jq -r .node_id <<< "$issue"); project=$(jq -r .project.id <<< "$snapshot")
    matches=$(jq -c --arg url "$url" --arg content "$content" '[.items[]|select(.content.url == $url or .content.id == $content)]' <<< "$snapshot")
    nexus_github_project_membership_matches "$matches" "$content" "$repo" "$url"
    plan=$(jq -cn --arg logical "$logical" --arg url "$url" --arg project "$project" --arg content "$content" '{provider:"github",operation:"project-item-add",repository:$logical,work_item_id:$url,metadata:{project_id:$project,content_id:$content}}')
    oid=$(printf '%s\n' "$plan" | git hash-object --stdin)
    if [[ "$apply" == false ]]; then
        [[ -z "$approved$approval" ]] || nexus_fail 'Approval flags require --apply.'
        jq -cn --argjson plan "$plan" --arg oid "$oid" --argjson present "$(jq 'length==1' <<< "$matches")" '{plan:$plan,plan_oid:$oid,applied:false,already_member:$present}'; return
    fi
    [[ "$approved" == "$oid" && -n "$approval" && "$approval" == *[![:space:]]* ]] || nexus_fail 'Exact membership plan digest and real human approval reference required.'
    if [[ $(jq length <<< "$matches") == 1 ]]; then
        jq -cn --arg oid "$oid" --arg approval "$approval" --arg item "$(jq -r '.[0].id' <<< "$matches")" '{applied:false,unchanged:true,observed:true,plan_oid:$oid,approval_reference:$approval,metadata:{item_id:$item}}'; return
    fi
    # At most one write. Even transport/GraphQL failure is followed by observation,
    # never replay; a recovered membership does not certify this mutation succeeded.
    if result=$(nexus_github_api graphql -f query='mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id project{id} content{... on Issue{id url repository{nameWithOwner}}}}}}' -f project="$project" -f content="$content"); then
        if jq -e --arg project "$project" --arg content "$content" --arg url "$url" --arg repo "$repo" '(.errors|length)==0 and (.data.addProjectV2ItemById.item.id|type == "string" and length>0) and .data.addProjectV2ItemById.item.project.id == $project and .data.addProjectV2ItemById.item.content.id == $content and .data.addProjectV2ItemById.item.content.url == $url and .data.addProjectV2ItemById.item.content.repository.nameWithOwner == $repo' <<< "$result" >/dev/null 2>&1; then valid=true; fi
    fi
    snapshot=$(nexus_github_project_snapshot "$mapping")
    jq -e --arg project "$project" '.project.id == $project' <<< "$snapshot" >/dev/null || nexus_fail 'Project identity changed after membership write; HOLD.'
    matches=$(jq -c --arg url "$url" --arg content "$content" '[.items[]|select(.content.url == $url or .content.id == $content)]' <<< "$snapshot")
    nexus_github_project_membership_matches "$matches" "$content" "$repo" "$url"
    [[ $(jq length <<< "$matches") == 1 ]] || nexus_fail 'Membership not observed after one write; preserve plan, reobserve, do not replay automatically.'
    received=$(jq -r '.data.addProjectV2ItemById.item.id // empty' <<< "$result" 2>/dev/null) || received=''
    if [[ -n "$received" ]]; then
        # A contradictory identified response cannot be reconciled as success.
        [[ "$valid" == true && "$received" == "$(jq -r '.[0].id' <<< "$matches")" ]] || nexus_fail 'Identified membership response contradicts observed target; HOLD and reconcile.'
    fi
    jq -cn --arg oid "$oid" --arg approval "$approval" --argjson valid "$valid" --arg item "$(jq -r '.[0].id' <<< "$matches")" '{applied:$valid,recovered:($valid|not),observed:true,plan_oid:$oid,approval_reference:$approval,metadata:{item_id:$item}}'
}
nexus_github_project_membership_matches() {
    jq -e --arg content "$2" --arg repo "$3" --arg url "$4" 'length<=1 and all(.[]; (.id|type == "string" and length>0) and .content.id == $content and .content.url == $url and .content.repository.nameWithOwner == $repo)' <<< "$1" >/dev/null || nexus_fail 'Duplicate or conflicting Project membership identity; HOLD.'
}
nexus_github_project_operation() {
    local op=$1 logical=$2 config=$3 request=$4 apply=$5 approved=$6 approval=$7 mapping snapshot field value expected matches item nativefield option current plan oid result NEXUS_GITHUB_REPOSITORY
    [[ "$op" == read || "$op" == field-update || "$op" == item-add ]] || nexus_fail 'Unsupported Project operation.'
    jq -e '.version == 1 and (.repositories|type == "object") and
      ([.repositories[].project | select(.number != null) | [.owner_kind,(.owner|ascii_downcase),.number]] as $ids | ($ids|unique|length) == ($ids|length))' "$config" >/dev/null || nexus_fail 'Invalid config or Project shared by multiple owning repositories.'
    mapping=$(jq -ec --arg logical "$logical" '.repositories[$logical] // error("Repository mapping absent")' "$config")
    NEXUS_GITHUB_REPOSITORY=$(jq -r .repository <<< "$mapping")
    jq -e '(.repository|type == "string" and test("^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")) and
      (.project.owner|type == "string" and test("^[A-Za-z0-9][A-Za-z0-9-]*$")) and
      (.project.number|type == "number" and floor == . and .>0) and
      (.project.fields.status.options|keys|sort) == (["Backlog","Ready","In Progress","Blocked","Review","Done"]|sort) and
      (.project.fields.priority.options|keys|sort) == ["P0","P1","P2","P3"]' <<< "$mapping" >/dev/null || nexus_fail 'Configure positive Project number, exact repository and all status/priority options.'
    snapshot=$(nexus_github_project_snapshot "$mapping")
    if [[ "$op" == read ]]; then
        [[ -z "$request$approved$approval" && "$apply" == false ]] || nexus_fail 'Read takes no request or approval.'
        # Native field IDs stay in metadata; externally visible values use canonical keys.
        jq --arg logical "$logical" '. as $s | {repository:$logical,project_url:.project.url,
          work_items:[.items[] | select(.content.repository.nameWithOwner == $s.mapping.repository) |
            . as $i | {work_item_id:.content.url,fields:($s.mapping.project.fields|to_entries|map(
              . as $m | [$i.fieldValues.nodes[]|select(.field.name == $m.value.name)] as $v |
              {key:$m.key,value:(if ($v|length)==0 then null
                elif ($v|length)>1 then error("Conflicting field observations") else
                  [$m.value.options|to_entries[]|select(.value == $v[0].name)|.key] as $values |
                  if ($values|length)==1 then $values[0] else error("Unmapped human field value") end end)})|from_entries),
              metadata:{external_item_id:.id}}],metadata:{project_id:.project.id}}' <<< "$snapshot"
        return
    fi
    if [[ "$op" == item-add ]]; then
        nexus_github_project_membership "$logical" "$mapping" "$snapshot" "$request" "$apply" "$approved" "$approval"; return
    fi
    [[ -f "$request" && -r "$request" ]] || nexus_fail 'Field update requires request JSON.'
    jq -e '(.field == "status" or .field == "priority") and (.value|type == "string") and has("expected_value") and
      (.expected_value == null or (.expected_value|type == "string")) and (.issue_url|type == "string")' "$request" >/dev/null || nexus_fail 'Invalid update request.'
    field=$(jq -r .field "$request"); value=$(jq -r .value "$request"); expected=$(jq -c .expected_value "$request")
    jq -e --arg field "$field" --arg value "$value" '.project.fields[$field].options|has($value)' <<< "$mapping" >/dev/null || nexus_fail 'Unsupported canonical field value.'
    matches=$(jq -c --arg url "$(jq -r .issue_url "$request")" --arg repo "$(jq -r .repository <<< "$mapping")" '[.items[]|select(.content.url == $url and .content.repository.nameWithOwner == $repo)]' <<< "$snapshot")
    [[ $(jq length <<< "$matches") == 1 ]] || nexus_fail 'Issue has no unique Project item; verify/add membership separately.'
    item=$(jq -c '.[0]' <<< "$matches")
    nativefield=$(jq -c --arg field "$field" '. as $s|.fields[]|select(.name == $s.mapping.project.fields[$field].name)' <<< "$snapshot")
    option=$(jq -r --arg field "$field" --arg value "$value" --argjson native "$nativefield" '.project.fields[$field].options[$value] as $name | $native.options[] | select(.name==$name)|.id' <<< "$mapping")
    current=$(jq -c --arg field "$field" --argjson item "$item" '.project.fields[$field] as $f | [$item.fieldValues.nodes[]|select(.field.name==$f.name)] as $values |
      if ($values|length)>1 then error("Conflicting field observations")
      elif ($values|length)==0 then null else
        [$f.options|to_entries[]|select(.value==$values[0].name)|.key] as $canonical |
        if ($canonical|length)==1 then $canonical[0] else error("Unmapped human field value") end end' <<< "$mapping")
    [[ "$current" == "$expected" || "$current" == "\"$value\"" ]] || nexus_fail 'Project field changed; reobserve and approve new plan.'
    plan=$(jq -cn --arg logical "$logical" --arg field "$field" --arg value "$value" --argjson expected "$expected" \
      --arg project "$(jq -r .project.id <<< "$snapshot")" --arg item "$(jq -r .id <<< "$item")" --arg nativefield "$(jq -r .id <<< "$nativefield")" --arg option "$option" \
      --arg url "$(jq -r .issue_url "$request")" '{provider:"github",operation:"project-field-update",repository:$logical,work_item_id:$url,field:$field,value:$value,expected_value:$expected,metadata:{project_id:$project,item_id:$item,field_id:$nativefield,option_id:$option}}')
    oid=$(printf '%s\n' "$plan" | git hash-object --stdin)
    if [[ "$apply" == false ]]; then
        [[ -z "$approved$approval" ]] || nexus_fail 'Approval flags require --apply.'
        jq -cn --argjson plan "$plan" --arg oid "$oid" '{plan:$plan,plan_oid:$oid,applied:false}'
        return
    fi
    [[ "$approved" == "$oid" && -n "$approval" && "$approval" == *[![:space:]]* ]] || nexus_fail 'Exact plan digest and real human approval reference required.'
    if [[ "$current" == "\"$value\"" ]]; then
        jq -cn --arg oid "$oid" '{applied:false,unchanged:true,plan_oid:$oid}'; return
    fi
    result=$(nexus_github_api graphql -f query='mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}' \
      -f project="$(jq -r .metadata.project_id <<< "$plan")" -f item="$(jq -r .metadata.item_id <<< "$plan")" \
      -f field="$(jq -r .metadata.field_id <<< "$plan")" -f option="$(jq -r .metadata.option_id <<< "$plan")") || nexus_fail 'Project write response unknown; preserve plan and reobserve, never replay blindly.'
    jq -e --arg id "$(jq -r .metadata.item_id <<< "$plan")" '(.errors|length)==0 and .data.updateProjectV2ItemFieldValue.projectV2Item.id == $id' <<< "$result" >/dev/null || nexus_fail 'Ambiguous Project mutation result; reobserve.'
    snapshot=$(nexus_github_project_snapshot "$mapping")
    jq -e --arg item "$(jq -r .metadata.item_id <<< "$plan")" --arg field "$(jq -r .metadata.field_id <<< "$plan")" --arg option "$option" \
      '[.items[]|select(.id==$item)|.fieldValues.nodes[]|select(.field.id==$field and .optionId==$option)]|length==1' <<< "$snapshot" >/dev/null || nexus_fail 'Requested field value not observed after mutation; reconcile.'
    jq -cn --arg oid "$oid" --arg approval "$approval" '{applied:true,observed:true,plan_oid:$oid,approval_reference:$approval}'
}
