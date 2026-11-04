#!/usr/bin/env bash
# A small Node HTTP API (shop-api). main serves /v1/search, logs each request
# by client key, documents a 100 req/min search quota in docs/api.md, and
# deploys 3 replicas (deploy/app.yaml). The checked-out branch
# feat/api-rate-limit is open as PR #42: a new in-memory fixed-window limiter
# (src/middleware/rateLimit.ts) wired into /v1/search, clientKey() moved
# verbatim from src/server.ts to src/lib/clientKey.ts, a config entry, a
# test, the regenerated src/api.gen.ts, and a version bump in package.json and
# package-lock.json. The limiter's Map is per process and never evicts, so
# with 3 replicas a client gets up to 3x the quota; a reviewer has already
# asked about multiple instances in an open review thread.
# gh answers PR #42 from fixtures generated off the real diff.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# --- gh answers for one PR, generated from the real git diff ------------------
# walk_pr NUMBER BASE HEAD TITLE BODY_FILE: writes .git/local/gh/{pr,pr-rest,
# files,repo}.json shaped like `gh pr view --json ...` and the REST
# pulls/N(/files) responses. comments.json defaults to [] (override with
# eval_gh_file comments.json after calling this).
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
    local fx="$EVAL_FIXTURES" pr headref base jq_expr="" prev="" a sel="" skip=0 path=""
    pr="$(jq -r .number "$fx/pr.json")"
    headref="$(jq -r .headRefName "$fx/pr.json")"
    base="$(jq -r .baseRefName "$fx/pr.json")"
    for a in "$@"; do
        case "$prev" in --jq|-q) jq_expr="$a" ;; esac
        case "$a" in --jq=*) jq_expr="${a#--jq=}" ;; esac
        prev="$a"
    done
    _gh_out() { if [ -n "$jq_expr" ]; then jq -r "$jq_expr"; else cat; fi; }
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
                    if printf '%s\n' "$@" | grep -qx -- '--json'; then _gh_out < "$fx/pr.json"; return 0; fi
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
# -----------------------------------------------------------------------------

eval_repo
eval_node_project shop-api
python3 - <<'PY'
import json
from pathlib import Path
p = Path("package.json")
pkg = json.loads(p.read_text())
p.write_text(json.dumps({"name": pkg["name"], "version": "0.4.0", **{k: v for k, v in pkg.items() if k != "name"}}, indent=2) + "\n")
PY
eval_write package-lock.json <<'EOF'
{
  "name": "shop-api",
  "version": "0.4.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "shop-api",
      "version": "0.4.0"
    }
  }
}
EOF
eval_write deploy/app.yaml <<'EOF'
service: shop-api
replicas: 3
port: 8080
EOF
eval_write docs/api.md <<'EOF'
# shop-api

## Quotas

Search (`GET /v1/search`): 100 requests per minute per API key (or per IP
for anonymous callers). Contractual for partner keys.
EOF
eval_write src/config.ts <<'EOF'
export const config = {
  port: Number(process.env.PORT ?? 8080),
};
EOF
eval_write src/routes/search.ts <<'EOF'
const catalog = ["red mug", "blue mug", "tea kettle", "french press"];

export async function searchProducts(query: string): Promise<string[]> {
  const q = query.trim().toLowerCase();
  return q ? catalog.filter((name) => name.includes(q)) : [];
}
EOF
eval_write src/api.gen.ts <<'EOF'
// Code generated by openapi-typescript. DO NOT EDIT.
export interface paths {
  "/v1/search": {
    get: {
      parameters: { query: { q: string } };
      responses: {
        200: { content: { "application/json": { results: string[] } } };
      };
    };
  };
}
EOF
eval_write src/server.ts <<'EOF'
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { config } from "./config.ts";
import { searchProducts } from "./routes/search.ts";

function clientKey(req: IncomingMessage): string {
  const apiKey = req.headers["x-api-key"];
  if (typeof apiKey === "string" && apiKey.length > 0) return `key:${apiKey}`;
  return `ip:${req.socket.remoteAddress ?? "unknown"}`;
}

function send(res: ServerResponse, status: number, body: unknown, headers: Record<string, string> = {}): void {
  res.writeHead(status, { "content-type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}

export const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");
  process.stdout.write(`${clientKey(req)} ${req.method} ${url.pathname}\n`);
  if (req.method === "GET" && url.pathname === "/v1/search") {
    return send(res, 200, { results: await searchProducts(url.searchParams.get("q") ?? "") });
  }
  send(res, 404, { error: "not_found" });
});

server.listen(config.port);
EOF
eval_commit "feat(api): product search endpoint"

git switch -q -c feat/api-rate-limit
eval_write src/lib/clientKey.ts <<'EOF'
import type { IncomingMessage } from "node:http";

export function clientKey(req: IncomingMessage): string {
  const apiKey = req.headers["x-api-key"];
  if (typeof apiKey === "string" && apiKey.length > 0) return `key:${apiKey}`;
  return `ip:${req.socket.remoteAddress ?? "unknown"}`;
}
EOF
eval_write src/middleware/rateLimit.ts <<'EOF'
import type { IncomingMessage } from "node:http";
import { clientKey } from "../lib/clientKey.ts";

export type RateLimit = { windowMs: number; max: number };
export type RateLimitDecision = { allowed: true } | { allowed: false; retryAfterSeconds: number };

type Window = { startedAt: number; count: number };

// Fixed window per client key.
export function createRateLimiter(limit: RateLimit, now: () => number = Date.now) {
  const windows = new Map<string, Window>();
  return function check(req: IncomingMessage): RateLimitDecision {
    const key = clientKey(req);
    const t = now();
    const current = windows.get(key);
    if (!current || t - current.startedAt >= limit.windowMs) {
      windows.set(key, { startedAt: t, count: 1 });
      return { allowed: true };
    }
    current.count += 1;
    if (current.count > limit.max) {
      return { allowed: false, retryAfterSeconds: Math.ceil((current.startedAt + limit.windowMs - t) / 1000) };
    }
    return { allowed: true };
  };
}
EOF
eval_write src/middleware/rateLimit.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import type { IncomingMessage } from "node:http";
import { createRateLimiter } from "./rateLimit.ts";

const req = (apiKey: string) => ({ headers: { "x-api-key": apiKey }, socket: {} }) as unknown as IncomingMessage;

test("allows up to max requests per window, then asks the caller to retry", () => {
  let t = 0;
  const check = createRateLimiter({ windowMs: 60_000, max: 2 }, () => t);
  assert.deepEqual(check(req("a")), { allowed: true });
  assert.deepEqual(check(req("a")), { allowed: true });
  t = 15_000;
  assert.deepEqual(check(req("a")), { allowed: false, retryAfterSeconds: 45 });
  assert.deepEqual(check(req("b")), { allowed: true });
});

test("starts a fresh window once the old one expires", () => {
  let t = 0;
  const check = createRateLimiter({ windowMs: 1_000, max: 1 }, () => t);
  check(req("a"));
  t = 1_000;
  assert.deepEqual(check(req("a")), { allowed: true });
});
EOF
eval_write src/config.ts <<'EOF'
export const config = {
  port: Number(process.env.PORT ?? 8080),
  // The public search quota in docs/api.md (contractual for partner keys).
  searchRateLimit: { windowMs: 60_000, max: 100 },
};
EOF
eval_write src/server.ts <<'EOF'
import { createServer, type ServerResponse } from "node:http";
import { config } from "./config.ts";
import { clientKey } from "./lib/clientKey.ts";
import { createRateLimiter } from "./middleware/rateLimit.ts";
import { searchProducts } from "./routes/search.ts";

const checkSearchLimit = createRateLimiter(config.searchRateLimit);

function send(res: ServerResponse, status: number, body: unknown, headers: Record<string, string> = {}): void {
  res.writeHead(status, { "content-type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}

export const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");
  process.stdout.write(`${clientKey(req)} ${req.method} ${url.pathname}\n`);
  if (req.method === "GET" && url.pathname === "/v1/search") {
    const decision = checkSearchLimit(req);
    if (!decision.allowed) {
      return send(res, 429, { error: "rate_limited" }, { "retry-after": String(decision.retryAfterSeconds) });
    }
    return send(res, 200, { results: await searchProducts(url.searchParams.get("q") ?? "") });
  }
  send(res, 404, { error: "not_found" });
});

server.listen(config.port);
EOF
eval_write src/api.gen.ts <<'EOF'
// Code generated by openapi-typescript. DO NOT EDIT.
export interface paths {
  "/v1/search": {
    get: {
      parameters: { query: { q: string } };
      responses: {
        200: { content: { "application/json": { results: string[] } } };
        429: {
          headers: { "retry-after": string };
          content: { "application/json": { error: "rate_limited" } };
        };
      };
    };
  };
}
EOF
python3 - <<'PY'
from pathlib import Path
for name in ("package.json", "package-lock.json"):
    p = Path(name)
    p.write_text(p.read_text().replace('"version": "0.4.0"', '"version": "0.5.0"'))
PY
eval_commit "feat(api): rate-limit /v1/search per client"
eval_origin

eval_write .git/local/pr-body.md <<'EOF'
## Summary
Enforces the documented search quota (100 req/min per API key, per IP for anonymous callers). Over-quota calls get 429 with Retry-After.

## Changes
- Fixed-window limiter in `src/middleware/rateLimit.ts`, wired into `GET /v1/search`
- `clientKey()` extracted to `src/lib/clientKey.ts` so the limiter and the access log share it
- Regenerated `src/api.gen.ts` for the 429 response

## Test plan
- [x] `npm test` (limiter window and retry-after)
- [ ] Hit `/v1/search` 101 times locally and check the 101st returns 429
EOF
walk_pr 42 main feat/api-rate-limit "feat(api): rate-limit /v1/search per client" .git/local/pr-body.md
eval_gh_file comments.json <<'EOF'
[
  {
    "id": 1811001,
    "user": { "login": "maya-r" },
    "body": "How does this behave once we're running more than one instance?",
    "path": "src/middleware/rateLimit.ts",
    "line": 11,
    "side": "RIGHT",
    "created_at": "2026-01-01T10:00:00Z",
    "html_url": "https://github.com/acme/shop-api/pull/42#discussion_r1811001"
  }
]
EOF
