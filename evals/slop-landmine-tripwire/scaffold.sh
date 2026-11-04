#!/usr/bin/env bash
# TypeScript service with src/profile-client.ts, a client for an upstream
# profile API. Planted: TIMEOUT_MS=5000, MAX_RETRIES=3, CONCURRENCY=20 with no
# receipt; retries on every error with no backoff; every upstream error is
# caught, logged and turned into an empty profile; a comment claims the
# upstream always returns a user id while the JSON is cast without
# validation. Decoy that is fine: MAX_IDS_PER_REQUEST=100 cites the upstream
# contract in docs/upstream-profile-api.md, which says exactly that (and says
# nothing about rate limits or latency, so those receipts are missing).
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project profile-gateway
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "node", "language": "typescript", "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write docs/upstream-profile-api.md <<'EOF'
# Upstream profile API (owned by the Identity team)

`GET /v2/profiles?ids=<comma-separated ids>`

- Returns `{ "profiles": [{ "userId": string, "displayName": string, "avatarUrl": string | null }] }`.
- Accepts at most 100 ids per request; more returns HTTP 414.
- Unknown ids are left out of the response.
EOF

eval_write src/logger.ts <<'EOF'
export const logger = {
  warn(message: string, fields: Record<string, unknown> = {}): void {
    process.stderr.write(`${JSON.stringify({ level: "warn", message, ...fields })}\n`);
  },
};
EOF

eval_write src/profile-client.ts <<'EOF'
import { logger } from "./logger.ts";

export type Profile = { userId: string; displayName: string; avatarUrl: string | null };

const BASE_URL = process.env.PROFILE_API_URL ?? "https://identity.internal";
const TIMEOUT_MS = 5000;
const MAX_RETRIES = 3;
const CONCURRENCY = 20;
// Upstream contract, docs/upstream-profile-api.md: at most 100 ids per request.
const MAX_IDS_PER_REQUEST = 100;

const EMPTY_PROFILE: Profile = { userId: "", displayName: "", avatarUrl: null };

async function fetchBatch(ids: readonly string[]): Promise<Profile[]> {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(`${BASE_URL}/v2/profiles?ids=${ids.join(",")}`, {
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // The upstream always returns a userId for every profile.
      const body = (await res.json()) as { profiles: Profile[] };
      return body.profiles;
    } catch (error) {
      if (attempt >= MAX_RETRIES) throw error;
    }
  }
}

export async function getProfiles(ids: readonly string[]): Promise<Map<string, Profile>> {
  const batches: string[][] = [];
  for (let i = 0; i < ids.length; i += MAX_IDS_PER_REQUEST) {
    batches.push(ids.slice(i, i + MAX_IDS_PER_REQUEST));
  }

  const profiles = new Map<string, Profile>();
  for (let i = 0; i < batches.length; i += CONCURRENCY) {
    const wave = batches.slice(i, i + CONCURRENCY);
    const results = await Promise.all(
      wave.map(async (batch) => {
        try {
          return await fetchBatch(batch);
        } catch (error) {
          logger.warn("profile fetch failed", { batchSize: batch.length, error: String(error) });
          return batch.map((userId) => ({ ...EMPTY_PROFILE, userId }));
        }
      }),
    );
    for (const profile of results.flat()) profiles.set(profile.userId, profile);
  }
  return profiles;
}
EOF

eval_write src/feed.ts <<'EOF'
import { getProfiles } from "./profile-client.ts";

export type FeedItem = { authorId: string; text: string };

export async function renderFeed(items: readonly FeedItem[]): Promise<string[]> {
  const profiles = await getProfiles([...new Set(items.map((item) => item.authorId))]);
  return items.map((item) => `${profiles.get(item.authorId)?.displayName ?? "Unknown"}: ${item.text}`);
}
EOF
eval_commit "feat: batch profile client for the feed"
eval_origin
eval_gh
