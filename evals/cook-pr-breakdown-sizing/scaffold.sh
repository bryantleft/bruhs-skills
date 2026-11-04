#!/usr/bin/env bash
# Next.js + Drizzle shop with users, purchases, refunds within a 30-day
# window, a nightly job runner, and an admin orders page. Nothing about
# referrals exists yet. Drizzle migrations live in drizzle/ (with the
# generated meta/_journal.json) and the schema in src/db/schema.ts.
# Refunds make purchase-time payouts risky and the nightly runner makes a
# batch job plausible, so payout timing is a real open question.
# docs/design/ holds one earlier doc.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project shop next react react-dom drizzle-orm drizzle-kit tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": ["drizzle"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write drizzle.config.ts <<'EOF'
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: { url: process.env.DATABASE_URL ?? "" },
});
EOF

eval_write src/db/schema.ts <<'EOF'
import { integer, pgEnum, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull().unique(),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});

export const purchaseStatus = pgEnum("purchase_status", ["pending", "completed", "refunded"]);

export const purchases = pgTable("purchases", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull().references(() => users.id),
  amountCents: integer("amount_cents").notNull(),
  status: purchaseStatus("status").notNull().default("pending"),
  completedAt: timestamp("completed_at"),
  refundedAt: timestamp("refunded_at"),
});
EOF

eval_write drizzle/0000_init.sql <<'EOF'
CREATE TABLE "users" (
	"id" text PRIMARY KEY NOT NULL,
	"email" text NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
EOF

eval_write drizzle/0001_purchases.sql <<'EOF'
CREATE TYPE "public"."purchase_status" AS ENUM('pending', 'completed', 'refunded');--> statement-breakpoint
CREATE TABLE "purchases" (
	"id" text PRIMARY KEY NOT NULL,
	"user_id" text NOT NULL,
	"amount_cents" integer NOT NULL,
	"status" "purchase_status" DEFAULT 'pending' NOT NULL,
	"completed_at" timestamp,
	"refunded_at" timestamp
);--> statement-breakpoint
ALTER TABLE "purchases" ADD CONSTRAINT "purchases_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");
EOF

eval_write drizzle/meta/_journal.json <<'EOF'
{
  "version": "7",
  "dialect": "postgresql",
  "entries": [
    { "idx": 0, "version": "7", "when": 1767225600000, "tag": "0000_init", "breakpoints": true },
    { "idx": 1, "version": "7", "when": 1772323200000, "tag": "0001_purchases", "breakpoints": true }
  ]
}
EOF

eval_write src/lib/db.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";

export const db = drizzle(process.env.DATABASE_URL ?? "");
EOF

eval_write src/purchases/hooks.ts <<'EOF'
export type CompletedPurchase = { readonly id: string; readonly userId: string; readonly amountCents: number; readonly completedAt: Date };

export type PurchaseHook = (purchase: CompletedPurchase) => Promise<void>;

/** Run, in order, after a purchase is marked completed. A throwing hook fails the request. */
export const onPurchaseCompleted: PurchaseHook[] = [];
EOF

eval_write src/purchases/complete-purchase.ts <<'EOF'
import { eq } from "drizzle-orm";
import { db } from "../lib/db.ts";
import { purchases } from "../db/schema.ts";
import { onPurchaseCompleted } from "./hooks.ts";

export async function completePurchase(purchaseId: string): Promise<void> {
  const completedAt = new Date();
  const [row] = await db
    .update(purchases)
    .set({ status: "completed", completedAt })
    .where(eq(purchases.id, purchaseId))
    .returning();
  if (!row) throw new Error(`completePurchase: no purchase ${purchaseId}`);
  for (const hook of onPurchaseCompleted) {
    await hook({ id: row.id, userId: row.userId, amountCents: row.amountCents, completedAt });
  }
}
EOF

eval_write src/purchases/refund.ts <<'EOF'
import { eq } from "drizzle-orm";
import { db } from "../lib/db.ts";
import { purchases } from "../db/schema.ts";

// Refund policy (support handbook §4): full refund within 30 days of purchase.
export const REFUND_WINDOW_DAYS = 30;

export async function refundPurchase(purchaseId: string, now = new Date()): Promise<void> {
  const [row] = await db.select().from(purchases).where(eq(purchases.id, purchaseId));
  if (!row || row.status !== "completed" || !row.completedAt) throw new Error(`refund: ${purchaseId} is not a completed purchase`);
  const ageDays = (now.getTime() - row.completedAt.getTime()) / 86_400_000;
  if (ageDays > REFUND_WINDOW_DAYS) throw new Error(`refund: ${purchaseId} is past the ${REFUND_WINDOW_DAYS}-day window`);
  await db.update(purchases).set({ status: "refunded", refundedAt: now }).where(eq(purchases.id, purchaseId));
}
EOF

eval_write src/jobs/nightly.ts <<'EOF'
// Runs every registered job once a night (cron: 02:00 UTC, see infra/cron.yaml).
export type NightlyJob = { readonly name: string; readonly run: (now: Date) => Promise<void> };

export const nightlyJobs: NightlyJob[] = [
  { name: "expire-pending-purchases", run: async () => {} },
];

export async function runNightly(now = new Date()): Promise<void> {
  for (const job of nightlyJobs) await job.run(now);
}
EOF

eval_write src/app/admin/orders/page.tsx <<'EOF'
import { desc } from "drizzle-orm";
import { requireAdmin } from "../../../lib/admin";
import { db } from "../../../lib/db";
import { purchases } from "../../../db/schema";

export default async function AdminOrdersPage() {
  await requireAdmin();
  const rows = await db.select().from(purchases).orderBy(desc(purchases.completedAt)).limit(50);
  return (
    <main className="p-6">
      <h1 className="mb-4 text-lg font-semibold">Orders</h1>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.status}</td>
              <td>{r.amountCents}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
EOF

eval_write src/lib/admin.ts <<'EOF'
export async function requireAdmin(): Promise<void> {
  // Session lookup elided; throws for non-admins.
}
EOF

eval_write docs/design/2026-06-02-cart-expiry.md <<'EOF'
# Expire abandoned pending purchases

**Status:** shipped · **Author:** Lee M · **Updated:** 2026-06-20

Pending purchases never expired, so stock stayed reserved. A nightly job now expires pending purchases older than 24 hours (the payment provider's own session expiry).

## Alternatives

| Option | Why not |
|---|---|
| Expire on read | Stock stays reserved until someone looks |
EOF

eval_commit "feat: purchases, refunds, nightly jobs and admin orders"
eval_origin
eval_gh
