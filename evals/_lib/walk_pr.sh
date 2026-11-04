# evals/_lib/walk_pr.sh — gh answers for one open PR, generated from the real
# git diff. Sourced by the walk-* scaffolds after helpers.sh.
#
# walk_pr NUMBER BASE HEAD TITLE BODY_FILE: writes .git/local/gh/{pr,pr-rest,
# files,repo}.json shaped like `gh pr view --json ...` and the REST
# pulls/N(/files) responses, then installs the stub gh that serves them
# (pr view/diff/checkout/list/status, repo view, and the pulls/N REST paths).
# comments.json defaults to [] (override with eval_gh_file comments.json after
# calling this). The repo is acme/shop-api and the author is jlee.
walk_pr() {
    mkdir -p .git/local/gh
    python3 - "$@" <<'PY'
import json, subprocess, sys
from pathlib import Path

num, base, head, title, body_file = sys.argv[1:6]
repo, login = "acme/shop-api", "jlee"
out = Path(".git/local/gh")

def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout

rng = f"{base}...{head}"
head_sha = git("rev-parse", head).strip()
kinds = {"A": ("added", "ADDED"), "M": ("modified", "MODIFIED"), "D": ("removed", "DELETED")}
status = {}
for line in git("diff", "--no-renames", "--name-status", rng).splitlines():
    code, path = line.split("\t", 1)
    status[path] = kinds[code[0]]
files, adds, dels = [], 0, 0
for line in git("diff", "--no-renames", "--numstat", rng).splitlines():
    a, d, path = line.split("\t", 2)
    a, d = int(a), int(d)
    adds, dels = adds + a, dels + d
    raw = git("diff", "--no-renames", rng, "--", path)
    at = raw.find("\n@@")
    rev = base if status[path][0] == "removed" else head
    files.append({
        "sha": git("rev-parse", f"{rev}:{path}").strip(),
        "filename": path,
        "status": status[path][0],
        "additions": a,
        "deletions": d,
        "changes": a + d,
        "blob_url": f"https://github.com/{repo}/blob/{head_sha}/{path}",
        "raw_url": f"https://github.com/{repo}/raw/{head_sha}/{path}",
        "patch": raw[at + 1:].rstrip("\n") if at >= 0 else "",
    })
commits = []
for line in git("log", "--reverse", "--format=%H%x09%s%x09%an%x09%ae", f"{base}..{head}").splitlines():
    oid, subject, name, email = line.split("\t")
    commits.append({"oid": oid, "messageHeadline": subject, "authors": [{"name": name, "email": email, "login": login}]})
body = Path(body_file).read_text().rstrip("\n")
url = f"https://github.com/{repo}/pull/{num}"
pr = {
    "number": int(num), "title": title, "body": body, "state": "OPEN", "isDraft": False, "url": url,
    "baseRefName": base, "headRefName": head, "headRefOid": head_sha,
    "additions": adds, "deletions": dels, "changedFiles": len(files),
    "author": {"login": login, "name": "Jordan Lee", "is_bot": False},
    "files": [{"path": f["filename"], "additions": f["additions"], "deletions": f["deletions"], "changeType": status[f["filename"]][1]} for f in files],
    "commits": commits, "comments": [], "reviews": [], "reviewDecision": "REVIEW_REQUIRED",
    "mergeable": "MERGEABLE", "createdAt": "2026-01-01T00:00:00Z",
}
rest = {
    "number": int(num), "title": title, "body": body, "state": "open", "draft": False, "html_url": url,
    "user": {"login": login}, "base": {"ref": base}, "head": {"ref": head, "sha": head_sha},
    "additions": adds, "deletions": dels, "changed_files": len(files), "commits": len(commits),
}
(out / "pr.json").write_text(json.dumps(pr, indent=2) + "\n")
(out / "pr-rest.json").write_text(json.dumps(rest, indent=2) + "\n")
(out / "files.json").write_text(json.dumps(files, indent=2) + "\n")
(out / "repo.json").write_text(json.dumps({"name": "shop-api", "owner": {"login": "acme"}, "nameWithOwner": repo, "url": f"https://github.com/{repo}", "defaultBranchRef": {"name": base}}) + "\n")
if not (out / "comments.json").exists():
    (out / "comments.json").write_text("[]\n")
PY
    eval_gh
    eval_gh_fixtures <<'SH'
gh_fixture() {
    local fx="$EVAL_FIXTURES" pr headref base jq_expr="" fields="" json=0 prev="" a sel="" skip=0 path=""
    pr="$(jq -r .number "$fx/pr.json")"
    headref="$(jq -r .headRefName "$fx/pr.json")"
    base="$(jq -r .baseRefName "$fx/pr.json")"
    for a in "$@"; do
        case "$prev" in --jq|-q) jq_expr="$a" ;; --json) fields="$a" ;; esac
        case "$a" in --jq=*) jq_expr="${a#--jq=}" ;; --json) json=1 ;; --json=*) json=1; fields="${a#--json=}" ;; esac
        prev="$a"
    done
    # Like real gh: keep only the --json fields, then apply --jq.
    _gh_out() {
        local data; data="$(cat)"
        if [ -n "$fields" ]; then
            data="$(printf '%s' "$data" | jq --arg f "$fields" '
                ($f | split(",") | map(gsub("^ +| +$"; ""))) as $k
                | def pick: with_entries(select(.key as $x | any($k[]; . == $x)));
                  if type == "array" then map(pick) else pick end')"
        fi
        if [ -n "$jq_expr" ]; then printf '%s' "$data" | jq -r "$jq_expr"; else printf '%s\n' "$data"; fi
    }
    _git() { git -C "$EVAL_DIR/../.." "$@"; }
    case "$1 ${2:-}" in
        "pr view"|"pr diff"|"pr checkout")
            for a in "${@:3}"; do
                if [ "$skip" = 1 ]; then skip=0; continue; fi
                case "$a" in
                    --json|--jq|-q|--template|-t|--repo|-R) skip=1 ;;
                    -*) ;;
                    *) sel="$a"; break ;;
                esac
            done
            case "$sel" in
                ""|"$pr"|"#$pr"|"$headref"|*/pull/"$pr") ;;
                *) echo "GraphQL: Could not resolve to a PullRequest with the number of $sel. (repository.pullRequest)" >&2; return 1 ;;
            esac
            case "$2" in
                view)
                    if [ "$json" = 1 ]; then _gh_out < "$fx/pr.json"; return 0; fi
                    jq -r '"\(.title) #\(.number)\nOpen • \(.author.login) wants to merge \(.commits | length) commit(s) into \(.baseRefName) from \(.headRefName) • +\(.additions) -\(.deletions)\n\n\(.body)\n\nView this pull request on GitHub: \(.url)"' "$fx/pr.json" ;;
                diff)
                    if printf '%s\n' "$@" | grep -qx -- '--name-only'; then _git diff --no-renames --name-only "$base...$headref"
                    else _git diff --no-renames "$base...$headref"; fi ;;
                checkout) _git switch -q "$headref" && echo "Switched to branch '$headref'" ;;
            esac ;;
        "pr list")
            jq '[{number, title, headRefName, baseRefName, url, state, author}]' "$fx/pr.json" | _gh_out ;;
        "pr status")
            jq -r '"Current branch\n  #\(.number)  \(.title) [\(.headRefName)]"' "$fx/pr.json" ;;
        "repo view")
            _gh_out < "$fx/repo.json" ;;
        "api "*)
            for a in "${@:2}"; do
                if [ "$skip" = 1 ]; then skip=0; continue; fi
                case "$a" in
                    -X|--method|-H|--header|-f|-F|--field|--raw-field|--jq|-q|--template|-t|--cache|-p|--preview|--hostname|--input) skip=1 ;;
                    -*) ;;
                    *) path="${a%%\?*}"; break ;;
                esac
            done
            case "$path" in
                */pulls/"$pr"/files) _gh_out < "$fx/files.json" ;;
                */pulls/"$pr"/comments) _gh_out < "$fx/comments.json" ;;
                */pulls/"$pr"/reviews|*/issues/"$pr"/comments) echo '[]' | _gh_out ;;
                */pulls/"$pr") _gh_out < "$fx/pr-rest.json" ;;
                *) return 127 ;;
            esac ;;
        *) return 127 ;;
    esac
}
SH
}
