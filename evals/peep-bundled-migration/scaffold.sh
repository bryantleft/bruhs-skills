#!/usr/bin/env bash
# Drizzle + Hono orders API. The user is on main; PR #412
# (feat/orders-status-filter, no comments, CI green) is small (about 60
# lines) and bundles a schema change with the code that uses it:
#   drizzle/0007_add_index_orders_status.sql   new migration (an index only)
#   drizzle/meta/_journal.json                 journal entry for it
#   src/db/schema.ts                           the index in the schema
#   src/orders/list.ts                         filter by status
#   src/orders/status.ts (+ test)              parse the ?status= filter
# The project rule (and peep's reviewer brief) says a migration ships in its
# own PR, merged first, regardless of size. Tests pass.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project orders-api hono drizzle-orm postgres
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Hono", "styling": [], "database": ["drizzle-postgres"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
eval_write src/db/schema.ts <<'EOF'
import { integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const orders = pgTable("orders", {
  id: text("id").primaryKey(),
  customerId: text("customer_id").notNull(),
  status: text("status", { enum: ["pending", "paid", "shipped", "cancelled"] }).notNull(),
  totalCents: integer("total_cents").notNull(),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});
EOF
eval_write src/db/client.ts <<'EOF'
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

export const db = drizzle(postgres(process.env.DATABASE_URL ?? ""));
EOF
eval_write src/orders/list.ts <<'EOF'
import { desc } from "drizzle-orm";
import { db } from "../db/client.ts";
import { orders } from "../db/schema.ts";

export async function listOrders(limit = 50) {
  return db.select().from(orders).orderBy(desc(orders.createdAt)).limit(limit);
}
EOF
journal() {
    # journal N: drizzle-kit's _journal.json with entries 0..N
    python3 - "$1" > drizzle/meta/_journal.json <<'PY'
import json, sys
names = ["init", "orders", "orders_customer_fk", "orders_total_cents", "orders_created_at", "drop_legacy_carts", "orders_status_enum", "add_index_orders_status"]
n = int(sys.argv[1])
entries = [{"idx": i, "version": "7", "when": 1767225600000 + i * 86400000, "tag": f"{i:04d}_{names[i]}", "breakpoints": True} for i in range(n + 1)]
print(json.dumps({"version": "7", "dialect": "postgresql", "entries": entries}, indent=2))
PY
}
mkdir -p drizzle/meta
for tag in 0000_init 0001_orders 0002_orders_customer_fk 0003_orders_total_cents \
           0004_orders_created_at 0005_drop_legacy_carts 0006_orders_status_enum; do
    printf -- '-- %s\nSELECT 1;\n' "$tag" > "drizzle/$tag.sql"
done
journal 6
eval_write drizzle.config.ts <<'EOF'
import { defineConfig } from "drizzle-kit";

export default defineConfig({ schema: "./src/db/schema.ts", out: "./drizzle", dialect: "postgresql" });
EOF
eval_commit "feat: orders schema and list endpoint"

git switch -q -c feat/orders-status-filter
eval_write drizzle/0007_add_index_orders_status.sql <<'EOF'
CREATE INDEX IF NOT EXISTS "orders_status_idx" ON "orders" USING btree ("status");
EOF
journal 7
eval_write src/db/schema.ts <<'EOF'
import { index, integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const orders = pgTable(
  "orders",
  {
    id: text("id").primaryKey(),
    customerId: text("customer_id").notNull(),
    status: text("status", { enum: ["pending", "paid", "shipped", "cancelled"] }).notNull(),
    totalCents: integer("total_cents").notNull(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
  },
  (t) => [index("orders_status_idx").on(t.status)],
);
EOF
eval_write src/orders/status.ts <<'EOF'
export const ORDER_STATUSES = ["pending", "paid", "shipped", "cancelled"] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

// `?status=paid` from the admin list; anything else means no filter.
export function parseStatusFilter(raw: string | null): OrderStatus | undefined {
  const value = raw?.trim().toLowerCase();
  return ORDER_STATUSES.find((s) => s === value);
}
EOF
eval_write src/orders/status.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseStatusFilter } from "./status.ts";

test("accepts known statuses case-insensitively", () => {
  assert.equal(parseStatusFilter(" Paid "), "paid");
});

test("ignores unknown or missing statuses", () => {
  assert.equal(parseStatusFilter("refunded"), undefined);
  assert.equal(parseStatusFilter(null), undefined);
});
EOF
eval_write src/orders/list.ts <<'EOF'
import { desc, eq } from "drizzle-orm";
import { db } from "../db/client.ts";
import { orders } from "../db/schema.ts";
import type { OrderStatus } from "./status.ts";

export async function listOrders(opts: { status?: OrderStatus; limit?: number } = {}) {
  const { status, limit = 50 } = opts;
  const query = db.select().from(orders);
  const filtered = status ? query.where(eq(orders.status, status)) : query;
  return filtered.orderBy(desc(orders.createdAt)).limit(limit);
}
EOF
eval_commit "feat(orders): filter the admin order list by status"
git switch -q main

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "orders-api", "nameWithOwner": "acme/orders-api", "owner": {"login": "acme"}, "url": "https://github.com/acme/orders-api", "defaultBranchRef": {"name": "main"}, "description": "Orders service."}
JSON
eval_gh_file pr-412.json <<'JSON'
{
  "number": 412,
  "title": "feat(orders): filter the admin order list by status",
  "body": "## What\n\n`listOrders` takes an optional `status`, parsed from `?status=` on the admin list. Adds an index on `orders.status` so the filtered query doesn't scan.\n\n## Test plan\n\n- [x] unit tests for parseStatusFilter\n- [x] `drizzle-kit generate` produced 0007 cleanly",
  "url": "https://github.com/acme/orders-api/pull/412",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "feat/orders-status-filter",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "typecheck", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/orders-api/actions/runs/412/job/1"},
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/orders-api/actions/runs/412/job/2"}
  ],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-03T10:00:00Z"
}
JSON
echo '[]' | eval_gh_file threads-412.json
echo '[]' | eval_gh_file review-comments-412.json
