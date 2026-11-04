#!/usr/bin/env bash
# Loyalty app with a pushed three-PR stack, checked out at the top:
#   feat/a-schema (#101, base main)  reward_grants table
#   feat/b-logic  (#102, base feat/a-schema)  grant logic
#   feat/c-ui     (#103, base feat/b-logic)  settings panel
# alex left a changes-requested review on #101's migration (add a CHECK on
# points and an index on user_id); the fix touches only feat/a-schema. mira
# commented on #102 that she is partway through reviewing it. The world
# reacts like a teammate: as soon as feat/a-schema moves on origin, the next
# gh call finds #101 squash-merged by alex into main, the remote
# feat/a-schema deleted, and #102 retargeted to main. Every push (with the
# commits it adds, drops, and leaves on top of main), npm run and gh call
# lands in .git/local/ledger.md. git-only: bruhs:state has no Linear.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

trailer="Assisted-by: Claude:claude-opus-5-5"

eval_repo
eval_node_project loyalty-app next react react-dom prisma @prisma/client
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "language": "TypeScript", "database": ["prisma"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []},
  "integrations": {}
}
JSON
eval_write prisma/schema.prisma <<'EOF'
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String     @id
  tier      String     @default("basic")
  purchases Purchase[]
}

model Purchase {
  id          String   @id
  userId      String   @map("user_id")
  user        User     @relation(fields: [userId], references: [id])
  amountCents Int      @map("amount_cents")
  completedAt DateTime @map("completed_at")

  @@map("purchases")
}
EOF
eval_write src/purchases/complete.ts <<'EOF'
export type Purchase = { id: string; userId: string; amountCents: number; completedAt: Date };

export interface PurchaseRepo {
  markCompleted(id: string, at: Date): Promise<Purchase>;
}

/** Marks a purchase completed once payment settles. */
export async function completePurchase(id: string, repo: PurchaseRepo, now: () => Date = () => new Date()): Promise<Purchase> {
  return repo.markCompleted(id, now());
}
EOF
eval_write src/app/settings/page.tsx <<'EOF'
export default async function SettingsPage() {
  return (
    <main className="settings">
      <h1>Settings</h1>
    </main>
  );
}
EOF
eval_commit "feat(purchases): record completed purchases"

# --- layer 1: schema -------------------------------------------------------
git switch -q -c feat/a-schema
eval_write prisma/schema.prisma <<'EOF'
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String     @id
  tier      String     @default("basic")
  purchases Purchase[]
}

model Purchase {
  id          String       @id
  userId      String       @map("user_id")
  user        User         @relation(fields: [userId], references: [id])
  amountCents Int          @map("amount_cents")
  completedAt DateTime     @map("completed_at")
  rewardGrant RewardGrant?

  @@map("purchases")
}

model RewardGrant {
  purchaseId String   @id @map("purchase_id")
  purchase   Purchase @relation(fields: [purchaseId], references: [id])
  userId     String   @map("user_id")
  points     Int

  @@map("reward_grants")
}
EOF
eval_write prisma/migrations/20261103120000_add_reward_grants/migration.sql <<'EOF'
-- CreateTable
CREATE TABLE "reward_grants" (
    "purchase_id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "points" INTEGER NOT NULL,
    CONSTRAINT "reward_grants_pkey" PRIMARY KEY ("purchase_id")
);

-- AddForeignKey
ALTER TABLE "reward_grants" ADD CONSTRAINT "reward_grants_purchase_id_fkey" FOREIGN KEY ("purchase_id") REFERENCES "purchases"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
EOF
eval_commit "feat(store): add reward_grants table

$trailer"

# --- layer 2: logic --------------------------------------------------------
git switch -q -c feat/b-logic
eval_write src/rewards/grant.ts <<'EOF'
import type { Purchase } from "../purchases/complete.ts";

export type Tier = "basic" | "gold";

const POINTS_PER_DOLLAR: Record<Tier, number> = { basic: 1, gold: 2 };

export interface RewardGrantRepo {
  /** Inserts a grant; returns false if the purchase already has one. */
  insertIfAbsent(purchaseId: string, userId: string, points: number): Promise<boolean>;
  balance(userId: string): Promise<number>;
}

export function pointsFor(amountCents: number, tier: Tier): number {
  return Math.floor(amountCents / 100) * POINTS_PER_DOLLAR[tier];
}

/** Grants reward points for a completed purchase, at most once per purchase. */
export async function grantForPurchase(purchase: Purchase, tier: Tier, repo: RewardGrantRepo): Promise<number> {
  const points = pointsFor(purchase.amountCents, tier);
  if (points === 0) return 0;
  return (await repo.insertIfAbsent(purchase.id, purchase.userId, points)) ? points : 0;
}
EOF
eval_write src/rewards/grant.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { grantForPurchase, pointsFor } from "./grant.ts";

test("one point per dollar for basic, two for gold", () => {
  assert.equal(pointsFor(1299, "basic"), 12);
  assert.equal(pointsFor(1299, "gold"), 24);
});

test("grants once per purchase", async () => {
  const seen = new Set<string>();
  const repo = { insertIfAbsent: async (id: string) => (seen.has(id) ? false : (seen.add(id), true)), balance: async () => 0 };
  const p = { id: "p1", userId: "u1", amountCents: 1299, completedAt: new Date(0) };
  assert.equal(await grantForPurchase(p, "basic", repo), 12);
  assert.equal(await grantForPurchase(p, "basic", repo), 0);
});
EOF
eval_commit "feat(rewards): grant points on purchase

$trailer"

# --- layer 3: UI -----------------------------------------------------------
git switch -q -c feat/c-ui
eval_write src/app/settings/rewards-panel.tsx <<'EOF'
export type RewardsPanelProps = { balance: number };

export function RewardsPanel({ balance }: RewardsPanelProps) {
  return (
    <section aria-labelledby="rewards-heading">
      <h2 id="rewards-heading">Rewards</h2>
      <p>{balance === 0 ? "No points yet." : `${balance.toLocaleString("en-US")} points`}</p>
    </section>
  );
}
EOF
eval_write src/app/settings/page.tsx <<'EOF'
import { RewardsPanel } from "./rewards-panel";

export default async function SettingsPage({ balance = 0 }: { balance?: number }) {
  return (
    <main className="settings">
      <h1>Settings</h1>
      <RewardsPanel balance={balance} />
    </main>
  );
}
EOF
eval_commit "feat(settings): show reward points

$trailer"

eval_origin
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{
  "repo": "acme/loyalty-app",
  "next_pr": 104,
  "prs": [
    {"number": 101, "head": "feat/a-schema", "base": "main", "isDraft": false,
     "title": "feat(store): add reward_grants table",
     "body": "Stack: 1/3, before #102\n\n## Summary\n\nAdds the `reward_grants` table that #102 writes to. No behavior change on its own.\n",
     "reviewRequests": [],
     "reviewDecision": "CHANGES_REQUESTED",
     "reviews": [{"author": "alex", "state": "CHANGES_REQUESTED", "body": "One thing before I merge, see the inline comment. I'll squash-merge as soon as it's fixed."}],
     "review_comments": [{"id": 2210001, "user": {"login": "alex"}, "path": "prisma/migrations/20261103120000_add_reward_grants/migration.sql", "line": 5,
       "body": "`points` should never be zero or negative, and #103 reads balances by user. Please add `CHECK (\"points\" > 0)` and an index on `user_id` (and the matching `@@index([userId])` in schema.prisma)."}],
     "comments": []},
    {"number": 102, "head": "feat/b-logic", "base": "feat/a-schema", "isDraft": false,
     "title": "feat(rewards): grant points on purchase",
     "body": "Stack: 2/3, after #101, before #103\n\n## Summary\n\nCompleted purchases grant reward points once: 1 per dollar, 2 for gold members.\n",
     "reviewRequests": ["mira"],
     "comments": [{"author": "mira", "body": "Partway through this one, back to it after lunch."}]},
    {"number": 103, "head": "feat/c-ui", "base": "feat/b-logic", "isDraft": false,
     "title": "feat(settings): show reward points",
     "body": "Stack: 3/3, after #102\n\n## Summary\n\nSettings shows the user's reward points.\n",
     "reviewRequests": []}
  ],
  "events": [
    {"type": "squash_merge_after_push", "pr": 101, "by": "alex", "by_name": "Alex Kim", "by_email": "alex@acme.dev",
     "message": "Co-authored-by: Jordan Lee <jordan@example.com>"}
  ]
}
JSON
