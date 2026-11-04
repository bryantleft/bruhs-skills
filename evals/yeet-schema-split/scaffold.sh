#!/usr/bin/env bash
# Prisma loyalty app on main with ~120 lines of uncommitted work: a Prisma
# migration plus schema.prisma change adding a small reward_grants table, and
# the grant-on-purchase logic that writes to it (src/rewards/grant.ts, its
# test, and a call from src/purchases/complete.ts). The bait: the diff is far
# under 400 lines and the table is tiny, so it looks fine as one PR. No PRs
# exist. bruhs:state has no Linear integration, so yeet runs git-only (one
# ticket per PR would otherwise collide: the Linear mock returns the same
# ticket for every create). typecheck, lint and test pass. Every push, npm
# run and gh call lands in .git/local/ledger.md.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

eval_repo
eval_node_project loyalty-app hono prisma @prisma/client
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Hono", "language": "TypeScript", "database": ["prisma"], "testing": ["node:test"], "tooling": []},
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
eval_write prisma/migrations/20261020090000_init/migration.sql <<'EOF'
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "tier" TEXT NOT NULL DEFAULT 'basic',
    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "purchases" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "amount_cents" INTEGER NOT NULL,
    "completed_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "purchases_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "purchases" ADD CONSTRAINT "purchases_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
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
eval_write src/purchases/complete.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { completePurchase } from "./complete.ts";

test("marks the purchase completed at the current time", async () => {
  const at = new Date("2026-11-03T12:00:00Z");
  const done = await completePurchase("p1", {
    markCompleted: async (id, when) => ({ id, userId: "u1", amountCents: 1200, completedAt: when }),
  }, () => at);
  assert.equal(done.completedAt, at);
});
EOF
eval_commit "feat(purchases): record completed purchases"
eval_origin

# The work to ship: reward points on purchase, plus the table they live in.
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
  points     Int

  @@map("reward_grants")
}
EOF
eval_write prisma/migrations/20261103120000_add_reward_grants/migration.sql <<'EOF'
-- CreateTable
CREATE TABLE "reward_grants" (
    "purchase_id" TEXT NOT NULL,
    "points" INTEGER NOT NULL,
    CONSTRAINT "reward_grants_pkey" PRIMARY KEY ("purchase_id")
);

-- AddForeignKey
ALTER TABLE "reward_grants" ADD CONSTRAINT "reward_grants_purchase_id_fkey" FOREIGN KEY ("purchase_id") REFERENCES "purchases"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
EOF
eval_write src/rewards/grant.ts <<'EOF'
import type { Purchase } from "../purchases/complete.ts";

export type Tier = "basic" | "gold";

/** Points per whole dollar spent, by tier. */
const POINTS_PER_DOLLAR: Record<Tier, number> = { basic: 1, gold: 2 };

export interface RewardGrantRepo {
  /** Inserts a grant for the purchase; returns false if one already exists (purchase_id is the primary key). */
  insertIfAbsent(purchaseId: string, points: number): Promise<boolean>;
}

export type GrantResult = { status: "granted"; points: number } | { status: "already_granted" } | { status: "nothing_to_grant" };

export function pointsFor(amountCents: number, tier: Tier): number {
  return Math.floor(amountCents / 100) * POINTS_PER_DOLLAR[tier];
}

/** Grants reward points for a completed purchase, at most once per purchase. */
export async function grantForPurchase(purchase: Purchase, tier: Tier, repo: RewardGrantRepo): Promise<GrantResult> {
  const points = pointsFor(purchase.amountCents, tier);
  if (points === 0) return { status: "nothing_to_grant" };
  const inserted = await repo.insertIfAbsent(purchase.id, points);
  return inserted ? { status: "granted", points } : { status: "already_granted" };
}
EOF
eval_write src/rewards/grant.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { grantForPurchase, pointsFor } from "./grant.ts";

const purchase = (amountCents: number) => ({ id: "p1", userId: "u1", amountCents, completedAt: new Date(0) });

function memoryRepo() {
  const grants = new Map<string, number>();
  return {
    grants,
    insertIfAbsent: async (id: string, points: number) => (grants.has(id) ? false : (grants.set(id, points), true)),
  };
}

test("one point per whole dollar for basic, two for gold", () => {
  assert.equal(pointsFor(1299, "basic"), 12);
  assert.equal(pointsFor(1299, "gold"), 24);
});

test("grants points once per purchase", async () => {
  const repo = memoryRepo();
  assert.deepEqual(await grantForPurchase(purchase(1299), "basic", repo), { status: "granted", points: 12 });
  assert.deepEqual(await grantForPurchase(purchase(1299), "basic", repo), { status: "already_granted" });
  assert.equal(repo.grants.get("p1"), 12);
});

test("purchases under a dollar earn nothing and write nothing", async () => {
  const repo = memoryRepo();
  assert.deepEqual(await grantForPurchase(purchase(99), "gold", repo), { status: "nothing_to_grant" });
  assert.equal(repo.grants.size, 0);
});
EOF
eval_write src/purchases/complete.ts <<'EOF'
import type { RewardGrantRepo, Tier } from "../rewards/grant.ts";
import { grantForPurchase } from "../rewards/grant.ts";

export type Purchase = { id: string; userId: string; amountCents: number; completedAt: Date };

export interface PurchaseRepo {
  markCompleted(id: string, at: Date): Promise<Purchase>;
  tierOf(userId: string): Promise<Tier>;
}

/** Marks a purchase completed once payment settles, then grants its reward points. */
export async function completePurchase(
  id: string,
  repo: PurchaseRepo,
  rewards: RewardGrantRepo,
  now: () => Date = () => new Date(),
): Promise<Purchase> {
  const purchase = await repo.markCompleted(id, now());
  await grantForPurchase(purchase, await repo.tierOf(purchase.userId), rewards);
  return purchase;
}
EOF
eval_write src/purchases/complete.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { completePurchase } from "./complete.ts";

test("marks the purchase completed and grants its points", async () => {
  const at = new Date("2026-11-03T12:00:00Z");
  const grants: Array<[string, number]> = [];
  const done = await completePurchase(
    "p1",
    {
      markCompleted: async (id, when) => ({ id, userId: "u1", amountCents: 1200, completedAt: when }),
      tierOf: async () => "gold",
    },
    { insertIfAbsent: async (id, points) => (grants.push([id, points]), true) },
    () => at,
  );
  assert.equal(done.completedAt, at);
  assert.deepEqual(grants, [["p1", 24]]);
});
EOF
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{ "repo": "acme/loyalty-app", "next_pr": 120 }
JSON
