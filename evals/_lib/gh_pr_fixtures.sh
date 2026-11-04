# gh_fixtures.sh: answers the gh calls bruhs makes about pull requests from
# data files in $EVAL_FIXTURES, written by this case's scaffold.sh:
#
#   repo.json                 gh repo view
#   me                        login of the authenticated user
#   pr-<n>.json               one PR with the fields bruhs reads; headRefOid,
#                             files, additions, deletions and changedFiles are
#                             read live from the local origin, so pushes show up
#   threads-<n>.json          reviewThreads nodes for the GraphQL query
#   review-comments-<n>.json  REST pulls/<n>/comments
#   issue-comments-<n>.json   REST issues/<n>/comments (optional)
#   on-view-<n>.sh            optional hook sourced before a PR is read
#
# Reads answer from those files. Writes (comment, review, merge, edit,
# replies, resolveReviewThread) succeed without changing anything; the stub's
# log (.git/local/gh-calls.log) records them. Anything else returns 127 and the
# stub reports "no fixture".

_ghx_origin() { printf '%s' "$EVAL_DIR/origin.git"; }
_ghx_me() { cat "$EVAL_FIXTURES/me" 2>/dev/null || echo jlee; }
_ghx_repo() { jq -r '.nameWithOwner' "$EVAL_FIXTURES/repo.json"; }

# Keep only the --json fields, then apply --jq. stdin: JSON.
_ghx_out() {
    local fields="$1" filter="$2" data
    data="$(cat)"
    if [ -n "$fields" ]; then
        data="$(printf '%s' "$data" | jq --arg f "$fields" '
            ($f | split(",") | map(gsub("^ +| +$"; ""))) as $k
            | def pick: with_entries(select(.key as $x | any($k[]; . == $x)));
              if type == "array" then map(pick) else pick end')"
    fi
    if [ -n "$filter" ]; then
        printf '%s' "$data" | jq -r "$filter"
    else
        printf '%s\n' "$data" | jq .
    fi
}

# PR number for a selector: a number, a URL, a branch, or empty (current branch).
_ghx_pr_number() {
    local sel="$1" f
    case "$sel" in
        "") sel="$(git branch --show-current)" ;;
        *"/pull/"*) sel="${sel##*/pull/}"; sel="${sel%%[/#?]*}" ;;
        "#"*) sel="${sel#\#}" ;;
    esac
    if [ -f "$EVAL_FIXTURES/pr-$sel.json" ]; then echo "$sel"; return 0; fi
    for f in "$EVAL_FIXTURES"/pr-*.json; do
        [ -f "$f" ] || continue
        if [ "$(jq -r .headRefName "$f")" = "$sel" ]; then jq -r .number "$f"; return 0; fi
    done
    return 1
}

# The PR as gh would return it now: static fields plus live git state.
_ghx_pr_live() {
    local n="$1" f="$EVAL_FIXTURES/pr-$1.json" head base oid origin
    [ -f "$EVAL_FIXTURES/on-view-$n.sh" ] && . "$EVAL_FIXTURES/on-view-$n.sh"
    origin="$(_ghx_origin)"
    head="$(jq -r .headRefName "$f")"
    base="$(jq -r '.baseRefName // "main"' "$f")"
    oid="$(git --git-dir="$origin" rev-parse "refs/heads/$head" 2>/dev/null || echo "")"
    git --git-dir="$origin" diff --numstat "$base...$head" 2>/dev/null \
        | jq -R -s --slurpfile pr "$f" --arg oid "$oid" '
            [split("\n")[] | select(length > 0) | split("\t")
             | {path: .[2], additions: (.[0] | tonumber? // 0), deletions: (.[1] | tonumber? // 0)}] as $files
            | $pr[0] + {
                headRefOid: $oid,
                files: $files,
                changedFiles: ($files | length),
                additions: ([$files[].additions] | add // 0),
                deletions: ([$files[].deletions] | add // 0)
              }'
}

# gh's errors when a selector matches no PR.
_ghx_no_pr() {
    case "$1" in
        "") echo "no pull requests found for branch \"$(git branch --show-current)\"" >&2 ;;
        *[!0-9#]*) echo "no pull requests found for branch \"$1\"" >&2 ;;
        *) echo "GraphQL: Could not resolve to a PullRequest with the number of ${1#\#}. (repository.pullRequest)" >&2 ;;
    esac
}

_ghx_pr_text() {
    jq -r '"\(.title) #\(.number)\n\(.state) • \(.author.login) wants to merge into \(.baseRefName) from \(.headRefName)\n\n\(.body)\n\nView this pull request on GitHub: \(.url)"'
}

gh_fixture() {
    local cmd="${1:-}"
    local fields="" filter="" pos=() method="" author="" headf="" basef="" state="open" search=""
    local nameonly="" query="" kv=() body=""
    [ $# -gt 0 ] && shift
    if [ "$cmd" != api ] && [ $# -gt 0 ]; then cmd="$cmd $1"; shift; fi
    while [ $# -gt 0 ]; do
        case "$1" in
            --json) fields="$2"; shift 2 ;;
            --json=*) fields="${1#*=}"; shift ;;
            -q|--jq) filter="$2"; shift 2 ;;
            --jq=*) filter="${1#*=}"; shift ;;
            -X|--method) method="$2"; shift 2 ;;
            --method=*|-X=*) method="${1#*=}"; shift ;;
            -A|--author) author="$2"; shift 2 ;;
            -H|--head) headf="$2"; shift 2 ;;
            -B|--base) basef="$2"; shift 2 ;;
            -s|--state) state="$2"; shift 2 ;;
            -S|--search) search="$2"; shift 2 ;;
            -f|-F|--field|--raw-field)
                kv+=("$2")
                case "$2" in query=*) query="${2#query=}" ;; body=*) body="${2#body=}" ;; esac
                shift 2 ;;
            -b|--body) body="$2"; shift 2 ;;
            --name-only) nameonly=1; shift ;;
            -t|--template|-R|--repo|-L|--limit|-l|--label|-T|--title|--add-reviewer|--body-file|--input|-e|--editor|--subject|--match-head-commit|--add-label|--remove-label|-r|--reviewer|-a|--assignee|-p|--paginate-limit)
                shift 2 ;;
            -*) shift ;;
            *) pos+=("$1"); shift ;;
        esac
    done
    local n repo me
    repo="$(_ghx_repo)"
    me="$(_ghx_me)"

    case "$cmd" in
    "repo view")
        if [ -n "$fields$filter" ]; then _ghx_out "$fields" "$filter" < "$EVAL_FIXTURES/repo.json"
        else jq -r '"\(.nameWithOwner)\n\(.description // "")"' "$EVAL_FIXTURES/repo.json"; fi ;;

    "pr view")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        if [ -n "$fields$filter" ]; then _ghx_pr_live "$n" | _ghx_out "$fields" "$filter"
        else _ghx_pr_live "$n" | _ghx_pr_text; fi ;;

    "pr diff")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        _ghx_pr_live "$n" >/dev/null
        local f="$EVAL_FIXTURES/pr-$n.json"
        git --git-dir="$(_ghx_origin)" diff ${nameonly:+--name-only} \
            "$(jq -r '.baseRefName // "main"' "$f")...$(jq -r .headRefName "$f")" ;;

    "pr checks")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        if [ -n "$fields$filter" ]; then
            _ghx_pr_live "$n" | jq '[.statusCheckRollup[] | {name, state: (.conclusion // .state), bucket: ((.conclusion // .state) | ascii_downcase | if . == "success" then "pass" elif . == "failure" then "fail" else "pending" end), link: (.detailsUrl // ""), workflow: (.workflowName // "")}]' \
                | _ghx_out "$fields" "$filter"
        else
            _ghx_pr_live "$n" | jq -r '.statusCheckRollup[] | "\(.name)\t\((.conclusion // .state) | ascii_downcase | if . == "success" then "pass" elif . == "failure" then "fail" else "pending" end)\t1m2s\t\(.detailsUrl // "")"'
        fi ;;

    "pr list")
        local all f
        all="$(for f in "$EVAL_FIXTURES"/pr-*.json; do [ -f "$f" ] && _ghx_pr_live "$(jq -r .number "$f")"; done | jq -s 'sort_by(-.number)')"
        [ "$author" = "@me" ] && author="$me"
        case "$search" in *"in:file"*) all="[]" ;; esac
        printf '%s' "$all" | jq --arg author "$author" --arg head "$headf" --arg base "$basef" \
            --arg state "$state" --arg search "$search" '
            [$search | split(" ")[] | select(length > 0 and (test(":") | not)) | ascii_downcase] as $terms
            | map(select(
                . as $pr
                | ($author == "" or $pr.author.login == $author)
                and ($head == "" or $pr.headRefName == $head)
                and ($base == "" or $pr.baseRefName == $base)
                and ($state == "all" or ($pr.state | ascii_downcase) == ($state | ascii_downcase)
                     or ($state == "closed" and $pr.state == "MERGED"))
                and (($pr.title + " " + $pr.body + " " + $pr.headRefName + " " + ($pr.number | tostring) | ascii_downcase) as $text
                     | all($terms[]; . as $w | $text | contains($w)))
            ))' | _ghx_out "$fields" "$filter" ;;

    "pr checkout")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        local head; head="$(jq -r .headRefName "$EVAL_FIXTURES/pr-$n.json")"
        git fetch -q origin "$head" && git switch "$head" ;;

    "pr comment")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        echo "https://github.com/$repo/pull/$n#issuecomment-90001" ;;
    "pr review")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        echo "✓ Reviewed pull request $repo#$n" ;;
    "pr merge")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        echo "✓ Squashed and merged pull request $repo#$n" ;;
    "pr edit"|"pr ready")
        n="$(_ghx_pr_number "${pos[0]:-}")" || { _ghx_no_pr "${pos[0]:-}"; return 1; }
        echo "https://github.com/$repo/pull/$n" ;;

    api)
        # the first positional after `api` is the endpoint
        local ep="${pos[0]:-}"
        [ -z "$method" ] && { [ ${#kv[@]} -gt 0 ] && [ "$ep" != graphql ] && method=POST || method=GET; }
        ep="${ep#/}"
        case "$ep" in
        graphql)
            case "$query" in
            *mutation*)
                case "$query" in
                *resolveReviewThread*) echo '{"data":{"resolveReviewThread":{"thread":{"isResolved":true}}}}' ;;
                *unresolveReviewThread*) echo '{"data":{"unresolveReviewThread":{"thread":{"isResolved":false}}}}' ;;
                *) echo '{"data":{"addPullRequestReviewThreadReply":{"comment":{"id":"PRRC_reply_1","url":"https://github.com/'"$repo"'/pull/0#discussion_r90001"}}}}' ;;
                esac ;;
            *reviewThreads*)
                n=""
                local p
                for p in "${kv[@]}"; do case "$p" in number=*|pr=*|prNumber=*|pull=*) n="${p#*=}" ;; esac; done
                [ -z "$n" ] && n="$(printf '%s' "$query" | sed -n 's/.*pullRequest(number: *\([0-9][0-9]*\).*/\1/p' | head -1)"
                [ -f "$EVAL_FIXTURES/pr-$n.json" ] || { echo "GraphQL: Could not resolve to a PullRequest with the number of $n." >&2; return 1; }
                jq '{data: {repository: {pullRequest: {reviewThreads: {totalCount: length, pageInfo: {hasNextPage: false, endCursor: null}, nodes: .}}}}}' \
                    "$EVAL_FIXTURES/threads-$n.json" 2>/dev/null | _ghx_out "" "$filter" ;;
            *viewer*) jq -n --arg l "$me" '{data: {viewer: {login: $l}}}' | _ghx_out "" "$filter" ;;
            *) return 127 ;;
            esac ;;
        user) jq -n --arg l "$me" '{login: $l, name: $l}' | _ghx_out "" "$filter" ;;
        repos/*/*/pulls/*/comments/*/replies|repos/*/*/pulls/comments/*/replies)
            jq -n --arg b "$body" --arg me "$me" '{id: 90001, body: $b, user: {login: $me}}' | _ghx_out "" "$filter" ;;
        repos/*/*/pulls/*/comments|repos/*/*/issues/*/comments|repos/*/*/pulls/*/reviews)
            n="$(printf '%s' "$ep" | cut -d/ -f5)"
            local kind; kind="$(printf '%s' "$ep" | cut -d/ -f4,6)"
            if [ "$method" != GET ]; then
                jq -n --arg b "$body" --arg me "$me" '{id: 90001, body: $b, user: {login: $me}}' | _ghx_out "" "$filter"
            else
                case "$kind" in
                pulls/comments) cat "$EVAL_FIXTURES/review-comments-$n.json" 2>/dev/null || echo '[]' ;;
                issues/comments) cat "$EVAL_FIXTURES/issue-comments-$n.json" 2>/dev/null || echo '[]' ;;
                pulls/reviews) _ghx_pr_live "$n" | jq '[.reviews[] | {id: 1, user: {login: .author.login}, state, body}]' ;;
                esac | _ghx_out "" "$filter"
            fi ;;
        repos/*/*/pulls/*/files)
            n="$(printf '%s' "$ep" | cut -d/ -f5)"
            _ghx_pr_live "$n" | jq '[.files[] | {filename: .path, additions, deletions, status: "modified"}]' | _ghx_out "" "$filter" ;;
        repos/*/*/pulls/*)
            n="$(printf '%s' "$ep" | cut -d/ -f5)"
            [ -f "$EVAL_FIXTURES/pr-$n.json" ] || return 127
            _ghx_pr_live "$n" | jq '{number, title, body, state: (.state | ascii_downcase), html_url: .url, user: {login: .author.login}, head: {ref: .headRefName, sha: .headRefOid}, base: {ref: .baseRefName}, draft: (.isDraft // false), mergeable: (.mergeable == "MERGEABLE")}' \
                | _ghx_out "" "$filter" ;;
        repos/*/*)
            jq '{full_name: .nameWithOwner, default_branch: .defaultBranchRef.name, html_url: .url}' "$EVAL_FIXTURES/repo.json" | _ghx_out "" "$filter" ;;
        *) return 127 ;;
        esac ;;

    *) return 127 ;;
    esac
}
