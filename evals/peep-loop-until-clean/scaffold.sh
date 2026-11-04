#!/usr/bin/env bash
# API client on branch feat/retry-api-calls with open PR #42, authored by the
# current user. No human comments, no reviews, and no AI-reviewer bot on the
# PR. CI is green. The diff adds src/lib/retry.ts:
#   - reproducible bug: the loop starts at 1, so retry(fn, 3) calls fn only
#     twice (a "fails twice, then succeeds" test throws on current code)
#   - nit: the doc comment says it retries "up to 5 times" but the default is 3
#   - second look: once the loop is fixed, the backoff sleeps after the last
#     failed attempt too, delaying the final error for nothing
# The shipped test only covers the first-try success path.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project status-client
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "framework": "Node", "styling": [], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
eval_write src/api/client.ts <<'EOF'
export type Status = { service: string; healthy: boolean };

export async function fetchStatus(baseUrl: string): Promise<Status[]> {
  const res = await fetch(`${baseUrl}/status`);
  if (!res.ok) throw new Error(`status request failed: ${res.status}`);
  return res.json();
}
EOF
eval_commit "feat: status API client"

git switch -q -c feat/retry-api-calls
eval_write src/lib/retry.ts <<'EOF'
export type RetryOptions = {
  attempts?: number;
  baseDelayMs?: number;
  sleep?: (ms: number) => Promise<void>;
};

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Calls `fn` until it resolves, retrying up to 5 times with exponential
 * backoff, then rethrows the last error.
 */
export async function retry<T>(fn: () => Promise<T>, opts: RetryOptions = {}): Promise<T> {
  const { attempts = 3, baseDelayMs = 200, sleep = defaultSleep } = opts;
  let lastError: unknown;
  for (let attempt = 1; attempt < attempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
    }
    await sleep(baseDelayMs * 2 ** (attempt - 1));
  }
  throw lastError;
}
EOF
eval_write src/lib/retry.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { retry } from "./retry.ts";

test("returns the first successful result", async () => {
  const result = await retry(async () => "ok", { sleep: async () => {} });
  assert.equal(result, "ok");
});
EOF
eval_write src/api/client.ts <<'EOF'
import { retry } from "../lib/retry.ts";

export type Status = { service: string; healthy: boolean };

// The status endpoint sheds load with 503s during deploys; retry those.
export async function fetchStatus(baseUrl: string): Promise<Status[]> {
  return retry(async () => {
    const res = await fetch(`${baseUrl}/status`);
    if (!res.ok) throw new Error(`status request failed: ${res.status}`);
    return res.json();
  });
}
EOF
eval_commit "feat: retry status requests with backoff"

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "status-client", "nameWithOwner": "acme/status-client", "owner": {"login": "acme"}, "url": "https://github.com/acme/status-client", "defaultBranchRef": {"name": "main"}, "description": "Client for the internal status API."}
JSON
eval_gh_file pr-42.json <<'JSON'
{
  "number": 42,
  "title": "feat: retry status requests with backoff",
  "body": "## What\n\n`fetchStatus` retries failed requests (default 3 attempts, exponential backoff from 200ms) via a small `retry` helper.\n\n## Why\n\nThe status endpoint returns 503 during deploys and the dashboard flashes red.\n\n## Test plan\n\n- [x] unit test for the success path",
  "url": "https://github.com/acme/status-client/pull/42",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "feat/retry-api-calls",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/status-client/actions/runs/42/job/1"}
  ],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-03T09:00:00Z"
}
JSON
echo '[]' | eval_gh_file threads-42.json
echo '[]' | eval_gh_file review-comments-42.json
echo '[]' | eval_gh_file issue-comments-42.json
