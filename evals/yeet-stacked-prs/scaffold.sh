#!/usr/bin/env bash
# Prisma + Next.js loyalty app. The checked-out branch feat/rewards (local
# only; origin has just main) holds three subjects: a reward_grants table
# (schema.prisma + migration), the grant logic (src/rewards/, wired into
# src/purchases/complete.ts) and a settings panel showing points
# (src/app/settings/rewards-panel.tsx + CSS + page.tsx). Its three WIP commits
# cut across subjects in the order they were written, so slicing by commit
# would mix layers. No PRs exist. bruhs:state has no Linear integration, so
# yeet runs git-only (the Linear mock returns the same ticket for every
# create, which three PRs would collide on). Every push, npm run and gh call
# (each PR's base, files, title and body) lands in .git/local/ledger.md.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

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
eval_write src/app/settings/page.tsx <<'EOF'
export default async function SettingsPage() {
  return (
    <main className="settings">
      <h1>Settings</h1>
      <section>
        <h2>Notifications</h2>
        <p>Weekly digest on</p>
      </section>
    </main>
  );
}
EOF
eval_commit "feat(purchases): record completed purchases"
eval_origin

git switch -q -c feat/rewards

# WIP 1: started on the grant logic, a first cut of the table, and a panel stub.
eval_write src/rewards/grant.ts <<'EOF'
import type { Purchase } from "../purchases/complete.ts";

export type Tier = "basic" | "gold";

/** Points per whole dollar spent, by tier. */
const POINTS_PER_DOLLAR: Record<Tier, number> = { basic: 1, gold: 2 };

export interface RewardGrantRepo {
  /** Inserts a grant for the purchase; returns false if one already exists (purchase_id is the primary key). */
  insertIfAbsent(purchaseId: string, userId: string, points: number): Promise<boolean>;
  /** Total points granted to a user. */
  balance(userId: string): Promise<number>;
}

export type GrantResult = { status: "granted"; points: number } | { status: "already_granted" } | { status: "nothing_to_grant" };

export function pointsFor(amountCents: number, tier: Tier): number {
  return Math.floor(amountCents / 100) * POINTS_PER_DOLLAR[tier];
}

/** Grants reward points for a completed purchase, at most once per purchase. */
export async function grantForPurchase(purchase: Purchase, tier: Tier, repo: RewardGrantRepo): Promise<GrantResult> {
  const points = pointsFor(purchase.amountCents, tier);
  if (points === 0) return { status: "nothing_to_grant" };
  const inserted = await repo.insertIfAbsent(purchase.id, purchase.userId, points);
  return inserted ? { status: "granted", points } : { status: "already_granted" };
}
EOF
eval_write prisma/migrations/20261103120000_add_reward_grants/migration.sql <<'EOF'
-- CreateTable
CREATE TABLE "reward_grants" (
    "purchase_id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "points" INTEGER NOT NULL,
    "granted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "reward_grants_pkey" PRIMARY KEY ("purchase_id")
);
EOF
eval_write src/app/settings/rewards-panel.tsx <<'EOF'
export function RewardsPanel() {
  return <section />;
}
EOF
eval_commit "wip: rewards"

# WIP 2: the panel and its styles.
eval_write src/app/settings/rewards-panel.tsx <<'EOF'
import styles from "./rewards-panel.module.css";

export type RewardsPanelProps = { balance: number; tier: "basic" | "gold" };

/** Shows the user's reward points and how they earn more. */
export function RewardsPanel({ balance, tier }: RewardsPanelProps) {
  const rate = tier === "gold" ? 2 : 1;
  return (
    <section className={styles.panel} aria-labelledby="rewards-heading">
      <h2 id="rewards-heading">Rewards</h2>
      {balance === 0 ? (
        <p className={styles.empty}>No points yet. You earn {rate} point{rate === 1 ? "" : "s"} for every dollar you spend.</p>
      ) : (
        <p className={styles.balance}>
          <strong>{balance.toLocaleString("en-US")}</strong> points
        </p>
      )}
      <p className={styles.rate}>
        {tier === "gold" ? "Gold members earn 2 points per dollar." : "Earn 1 point per dollar. Gold members earn 2."}
      </p>
    </section>
  );
}
EOF
eval_write src/app/settings/rewards-panel.module.css <<'EOF'
.panel {
  margin-top: 1.5rem;
  padding: 1rem 1.25rem;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 0.75rem;
}

.balance strong {
  font-size: 1.5rem;
  font-variant-numeric: tabular-nums;
}

.empty,
.rate {
  color: var(--muted, #6b7280);
}

@media (max-width: 480px) {
  .panel {
    padding: 0.75rem;
  }
}
EOF
eval_write src/app/settings/page.tsx <<'EOF'
import { RewardsPanel } from "./rewards-panel";
import { getRewardsSummary } from "../../rewards/summary";

export default async function SettingsPage() {
  const rewards = await getRewardsSummary();
  return (
    <main className="settings">
      <h1>Settings</h1>
      <section>
        <h2>Notifications</h2>
        <p>Weekly digest on</p>
      </section>
      <RewardsPanel balance={rewards.balance} tier={rewards.tier} />
    </main>
  );
}
EOF
eval_commit "wip ui"

# WIP 3: schema.prisma caught up, FK added, tests, and the purchase wiring.
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
  grantedAt  DateTime @default(now()) @map("granted_at")

  @@index([userId])
  @@map("reward_grants")
}
EOF
eval_write prisma/migrations/20261103120000_add_reward_grants/migration.sql <<'EOF'
-- CreateTable
CREATE TABLE "reward_grants" (
    "purchase_id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "points" INTEGER NOT NULL,
    "granted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "reward_grants_pkey" PRIMARY KEY ("purchase_id")
);

-- CreateIndex
CREATE INDEX "reward_grants_user_id_idx" ON "reward_grants"("user_id");

-- AddForeignKey
ALTER TABLE "reward_grants" ADD CONSTRAINT "reward_grants_purchase_id_fkey" FOREIGN KEY ("purchase_id") REFERENCES "purchases"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
EOF
eval_write src/rewards/summary.ts <<'EOF'
import type { RewardGrantRepo, Tier } from "./grant.ts";

export type RewardsSummary = { balance: number; tier: Tier };

let repo: RewardGrantRepo | undefined;
let currentUser: { id: string; tier: Tier } | undefined;

/** Wired at startup; the settings page reads through it. */
export function configureRewards(r: RewardGrantRepo, user: { id: string; tier: Tier }): void {
  repo = r;
  currentUser = user;
}

export async function getRewardsSummary(): Promise<RewardsSummary> {
  if (!repo || !currentUser) throw new Error("rewards not configured: call configureRewards() at startup");
  return { balance: await repo.balance(currentUser.id), tier: currentUser.tier };
}
EOF
eval_write src/rewards/grant.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { grantForPurchase, pointsFor } from "./grant.ts";

const purchase = (amountCents: number) => ({ id: "p1", userId: "u1", amountCents, completedAt: new Date(0) });

function memoryRepo() {
  const grants = new Map<string, { userId: string; points: number }>();
  return {
    grants,
    insertIfAbsent: async (id: string, userId: string, points: number) =>
      grants.has(id) ? false : (grants.set(id, { userId, points }), true),
    balance: async (userId: string) => [...grants.values()].filter((g) => g.userId === userId).reduce((s, g) => s + g.points, 0),
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
  assert.equal(await repo.balance("u1"), 12);
});

test("purchases under a dollar earn nothing and write nothing", async () => {
  const repo = memoryRepo();
  assert.deepEqual(await grantForPurchase(purchase(99), "gold", repo), { status: "nothing_to_grant" });
  assert.equal(repo.grants.size, 0);
});
EOF
eval_write src/rewards/summary.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { configureRewards, getRewardsSummary } from "./summary.ts";

test("summary reads the configured user's balance", async () => {
  configureRewards({ insertIfAbsent: async () => true, balance: async (id) => (id === "u1" ? 340 : 0) }, { id: "u1", tier: "gold" });
  assert.deepEqual(await getRewardsSummary(), { balance: 340, tier: "gold" });
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
    { insertIfAbsent: async (id, _user, points) => (grants.push([id, points]), true), balance: async () => 0 },
    () => at,
  );
  assert.equal(done.completedAt, at);
  assert.deepEqual(grants, [["p1", 24]]);
});
EOF
eval_commit "fix schema + tests"

eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{ "repo": "acme/loyalty-app", "next_pr": 101 }
JSON
