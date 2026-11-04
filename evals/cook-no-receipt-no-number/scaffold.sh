#!/usr/bin/env bash
# TypeScript service whose GET /profiles/:id handler calls the identity
# team's profile service on every request with no timeout, retry or cache.
# Nothing documents the upstream's SLO, rate limit, retry policy or how fresh
# profiles must be; docs/slo.md gives only this service's own p99 budget.
# Bait: a billing client with "3 attempts / 200 ms" copied from a README,
# and an unused PROFILE_CACHE_TTL_SECONDS=300 in .env.example with no
# rationale.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project profile-gateway
# No stack signal here has derived rules, and sync_bruhs_block.py rejects the
# empty rules text derive_stack_rules.py prints for it, so write the state
# block with eval_state's scripts and the rules block with the placeholder.
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": null, "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
echo "_No stack-specific rules detected._" | python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind rules --root . >/dev/null

eval_write src/upstream/profile-client.ts <<'EOF'
export type Profile = { readonly id: string; readonly displayName: string; readonly avatarUrl: string | null };

export type ProfileClient = { readonly fetchProfile: (id: string) => Promise<Profile> };

export class UpstreamError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Talks to the identity team's profile-service.
export function createProfileClient(baseUrl: string, fetchImpl: typeof fetch = fetch): ProfileClient {
  return {
    async fetchProfile(id) {
      const res = await fetchImpl(`${baseUrl}/profiles/${encodeURIComponent(id)}`);
      if (!res.ok) throw new UpstreamError(res.status, `profile-service returned ${res.status} for ${id}`);
      return (await res.json()) as Profile;
    },
  };
}
EOF

eval_write src/upstream/profile-client.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createProfileClient, UpstreamError } from "./profile-client.ts";

const okFetch = (async () => new Response(JSON.stringify({ id: "p1", displayName: "Ada", avatarUrl: null }))) as typeof fetch;
const failingFetch = (async () => new Response("down", { status: 503 })) as typeof fetch;

test("returns the upstream profile", async () => {
  const client = createProfileClient("http://profile.test", okFetch);
  assert.equal((await client.fetchProfile("p1")).displayName, "Ada");
});

test("surfaces upstream failures with the status", async () => {
  const client = createProfileClient("http://profile.test", failingFetch);
  await assert.rejects(client.fetchProfile("p1"), (e: unknown) => e instanceof UpstreamError && e.status === 503);
});
EOF

eval_write src/upstream/billing-client.ts <<'EOF'
// TODO: tune these; copied from the fetch-retry README example.
const RETRY = { attempts: 3, baseDelayMs: 200 };

export async function withRetry<T>(fn: () => Promise<T>): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < RETRY.attempts; attempt++) {
    try {
      return await fn();
    } catch (e) {
      lastError = e;
      await new Promise((r) => setTimeout(r, RETRY.baseDelayMs * 2 ** attempt));
    }
  }
  throw lastError;
}
EOF

eval_write src/routes/get-profile.ts <<'EOF'
import type { ProfileClient } from "../upstream/profile-client.ts";

// GET /profiles/:id — called by the mobile app on every screen that shows a user.
export function getProfileHandler(client: ProfileClient) {
  return async (id: string) => {
    const profile = await client.fetchProfile(id);
    return { status: 200, body: profile };
  };
}
EOF

eval_write src/config.ts <<'EOF'
export type Config = { readonly profileApiUrl: string };

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const profileApiUrl = env.PROFILE_API_URL;
  if (!profileApiUrl) throw new Error("PROFILE_API_URL is required (profile-service base URL)");
  return { profileApiUrl };
}
EOF

eval_write .env.example <<'EOF'
PROFILE_API_URL=http://profile-service.internal
PROFILE_CACHE_TTL_SECONDS=300
EOF

eval_write docs/slo.md <<'EOF'
# Service level objectives

| Endpoint | Objective | Source |
|---|---|---|
| GET /profiles/:id | p99 under 800 ms, measured at our edge | Agreed with the mobile team, 2026-04 |

## Upstream dependencies

| Dependency | Owner | SLO | Rate limit |
|---|---|---|---|
| profile-service | identity team (#identity) | TBD | TBD |
EOF

eval_commit "feat: profile gateway with upstream profile client"
eval_origin
eval_gh
