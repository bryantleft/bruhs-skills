#!/usr/bin/env bash
# shop-api with 22 thin service modules over src/lib/http.ts. The checked-out
# branch feat/upstream-retries is open as PR #57 (26 files): a new
# retry/backoff client (src/lib/retryClient.ts, the only real logic), http.ts
# routed through it, its test, a tsconfig "@/*" path alias, and a codemod that
# changes only the import line in all 22 src/services/*.ts files. The landmine:
# retries apply to postJson too, so createCharge in src/services/payments.ts
# (no idempotency key) can charge twice after a timeout or 5xx.
# gh answers PR #57 from fixtures generated off the real diff.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"
. "$(cd "$(dirname "$0")" && pwd)/../_lib/walk_pr.sh"

SERVICES="accounts addresses analytics carts catalog coupons currencies emails fulfillment giftCards inventory invoices loyalty notifications orders payments pricing recommendations returns reviews shipping taxes"

write_service() { # NAME IMPORT_PATH
    local name="$1" from="$2" type
    type="$(printf '%s' "${name:0:1}" | tr '[:lower:]' '[:upper:]')${name:1}"
    case "$name" in
        payments)
            eval_write "src/services/$name.ts" <<EOF
import { getJson, postJson } from "$from";

export type ChargeInput = { orderId: string; amountCents: number; currency: string; paymentMethodId: string };

export async function createCharge(input: ChargeInput): Promise<unknown> {
  return postJson("https://payments.internal/v1/charges", input);
}

export async function getCharge(id: string): Promise<unknown> {
  return getJson(\`https://payments.internal/v1/charges/\${encodeURIComponent(id)}\`);
}
EOF
            ;;
        emails|orders)
            eval_write "src/services/$name.ts" <<EOF
import { getJson, postJson } from "$from";

export async function create${type%s}(body: Record<string, unknown>): Promise<unknown> {
  return postJson("https://$name.internal/v1/$name", body);
}

export async function get${type%s}(id: string): Promise<unknown> {
  return getJson(\`https://$name.internal/v1/$name/\${encodeURIComponent(id)}\`);
}
EOF
            ;;
        *)
            eval_write "src/services/$name.ts" <<EOF
import { getJson } from "$from";

export async function get${type}(id: string): Promise<unknown> {
  return getJson(\`https://$name.internal/v1/$name/\${encodeURIComponent(id)}\`);
}
EOF
            ;;
    esac
}

eval_repo
eval_node_project shop-api
eval_write tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "strict": true,
    "allowImportingTsExtensions": true,
    "noEmit": true
  },
  "include": ["src"]
}
EOF
eval_write src/lib/http.ts <<'EOF'
export async function getJson(url: string): Promise<unknown> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} answered HTTP ${res.status}`);
  return res.json();
}

export async function postJson(url: string, body: unknown): Promise<unknown> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${url} answered HTTP ${res.status}`);
  return res.json();
}
EOF
for s in $SERVICES; do write_service "$s" "../lib/http.ts"; done
eval_commit "feat(services): thin clients for upstream services"

git switch -q -c feat/upstream-retries
eval_write src/lib/retryClient.ts <<'EOF'
export type RetryPolicy = {
  attempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  timeoutMs: number;
};

// Starting values until we have upstream latency data; see the PR description.
export const defaultRetryPolicy: RetryPolicy = {
  attempts: 4,
  baseDelayMs: 200,
  maxDelayMs: 5_000,
  timeoutMs: 10_000,
};

const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

export class UpstreamError extends Error {
  readonly status: number | undefined;
  readonly attempts: number;

  constructor(message: string, status: number | undefined, attempts: number) {
    super(message);
    this.name = "UpstreamError";
    this.status = status;
    this.attempts = attempts;
  }
}

type Sleep = (ms: number) => Promise<void>;
const realSleep: Sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function backoffDelay(policy: RetryPolicy, attempt: number, random: () => number): number {
  const exponential = policy.baseDelayMs * 2 ** (attempt - 1);
  const capped = Math.min(exponential, policy.maxDelayMs);
  return Math.round(capped / 2 + random() * (capped / 2));
}

function retryAfterMs(res: Response): number | undefined {
  const header = res.headers.get("retry-after");
  if (header === null) return undefined;
  const seconds = Number(header);
  if (Number.isFinite(seconds)) return seconds * 1000;
  const date = Date.parse(header);
  return Number.isNaN(date) ? undefined : Math.max(0, date - Date.now());
}

function isRetryableError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "TimeoutError") return true;
  return err instanceof TypeError; // fetch reports network failures as TypeError
}

export async function retryingFetch(
  url: string,
  init: RequestInit = {},
  policy: RetryPolicy = defaultRetryPolicy,
  deps: { fetch?: typeof fetch; sleep?: Sleep; random?: () => number } = {},
): Promise<Response> {
  const doFetch = deps.fetch ?? fetch;
  const sleep = deps.sleep ?? realSleep;
  const random = deps.random ?? Math.random;
  const method = init.method ?? "GET";

  for (let attempt = 1; ; attempt++) {
    let res: Response;
    try {
      res = await doFetch(url, { ...init, signal: AbortSignal.timeout(policy.timeoutMs) });
    } catch (err) {
      if (!isRetryableError(err) || attempt >= policy.attempts) {
        throw new UpstreamError(`${method} ${url} failed after ${attempt} attempt(s): ${String(err)}`, undefined, attempt);
      }
      await sleep(backoffDelay(policy, attempt, random));
      continue;
    }
    if (res.ok) return res;
    if (!RETRYABLE_STATUS.has(res.status) || attempt >= policy.attempts) {
      throw new UpstreamError(`${method} ${url} answered HTTP ${res.status} after ${attempt} attempt(s)`, res.status, attempt);
    }
    await sleep(retryAfterMs(res) ?? backoffDelay(policy, attempt, random));
  }
}
EOF
eval_write src/lib/http.ts <<'EOF'
import { retryingFetch } from "./retryClient.ts";

export async function getJson(url: string): Promise<unknown> {
  const res = await retryingFetch(url);
  return res.json();
}

export async function postJson(url: string, body: unknown): Promise<unknown> {
  const res = await retryingFetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}
EOF
eval_write src/lib/retryClient.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { retryingFetch, UpstreamError, type RetryPolicy } from "./retryClient.ts";

const policy: RetryPolicy = { attempts: 3, baseDelayMs: 100, maxDelayMs: 1_000, timeoutMs: 1_000 };
const noSleep = async () => {};

function scripted(...statuses: number[]) {
  let calls = 0;
  const fetch = (async () => new Response("{}", { status: statuses[calls++] ?? 200 })) as typeof globalThis.fetch;
  return { fetch, calls: () => calls };
}

test("retries a 503 and returns the first success", async () => {
  const upstream = scripted(503, 503, 200);
  const res = await retryingFetch("https://x.internal", {}, policy, { fetch: upstream.fetch, sleep: noSleep });
  assert.equal(res.status, 200);
  assert.equal(upstream.calls(), 3);
});

test("does not retry a 400", async () => {
  const upstream = scripted(400);
  await assert.rejects(retryingFetch("https://x.internal", {}, policy, { fetch: upstream.fetch, sleep: noSleep }), UpstreamError);
  assert.equal(upstream.calls(), 1);
});

test("gives up after the last attempt", async () => {
  const upstream = scripted(500, 500, 500, 200);
  await assert.rejects(retryingFetch("https://x.internal", {}, policy, { fetch: upstream.fetch, sleep: noSleep }), /after 3 attempt/);
});
EOF
python3 - <<'PY'
import json
from pathlib import Path
p = Path("tsconfig.json")
cfg = json.loads(p.read_text())
cfg["compilerOptions"]["baseUrl"] = "."
cfg["compilerOptions"]["paths"] = {"@/*": ["./src/*"]}
p.write_text(json.dumps(cfg, indent=2) + "\n")
PY
for s in $SERVICES; do
    python3 - "src/services/$s.ts" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
p.write_text(p.read_text().replace('from "../lib/http.ts"', 'from "@/lib/http.ts"'))
PY
done
git add -A
git commit -q -m "feat(http): retry upstream calls with backoff"
eval_origin

eval_write .git/local/pr-body.md <<'EOF'
## Summary
Upstream calls retry transient failures (network errors, timeouts, 408/429/5xx) with capped exponential backoff and jitter, honoring Retry-After. Every service goes through `src/lib/http.ts`, so all 22 get it.

Also switches `src/services/*` to the new `@/lib` path alias (codemod, import lines only).

## Test plan
- [x] `npm test` covers retry-then-success, no retry on 400, and giving up after the last attempt
EOF
walk_pr 57 main feat/upstream-retries "feat(http): retry upstream calls with backoff" .git/local/pr-body.md
