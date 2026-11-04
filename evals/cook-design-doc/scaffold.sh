#!/usr/bin/env bash
# Fleet platform (TypeScript + Drizzle/Postgres) where every balance read hits
# the primary. Two owners read balances (.github/CODEOWNERS): the dashboard
# team, on every page load, and the billing team, which reads a balance and
# then charges against it (src/billing/charge.ts), so stale reads there would
# overdraw fleets. docs/design/ holds one earlier doc that sets the naming.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project fleet-platform drizzle-orm pg
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": null, "database": ["drizzle", "postgres"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write .github/CODEOWNERS <<'EOF'
/src/dashboard/  @acme/fleet-dashboard
/src/billing/    @acme/billing
/src/balances/   @acme/platform
/src/db/         @acme/platform
EOF

eval_write src/db/schema.ts <<'EOF'
import { bigint, index, pgTable, text, timestamp } from "drizzle-orm/pg-core";

// One row per fleet per balance change; the current balance is the latest row.
export const fleetBalances = pgTable(
  "fleet_balances",
  {
    id: text("id").primaryKey(),
    fleetId: text("fleet_id").notNull(),
    balanceCents: bigint("balance_cents", { mode: "number" }).notNull(),
    recordedAt: timestamp("recorded_at").notNull().defaultNow(),
  },
  (t) => [index("fleet_balances_fleet_recorded_idx").on(t.fleetId, t.recordedAt)],
);

export const ledgerEntries = pgTable("ledger_entries", {
  id: text("id").primaryKey(),
  fleetId: text("fleet_id").notNull(),
  amountCents: bigint("amount_cents", { mode: "number" }).notNull(),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});
EOF

eval_write src/db/client.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

// The only connection the app has. There is no replica configured yet.
export const primary = drizzle(new Pool({ connectionString: process.env.DATABASE_URL }));
EOF

eval_write src/balances/read.ts <<'EOF'
import { desc, eq, inArray } from "drizzle-orm";
import { primary } from "../db/client.ts";
import { fleetBalances } from "../db/schema.ts";

export type FleetBalance = { readonly fleetId: string; readonly balanceCents: number; readonly recordedAt: Date };

// Shared by the dashboard and billing.
export async function getFleetBalance(fleetId: string): Promise<FleetBalance | undefined> {
  const [row] = await primary
    .select()
    .from(fleetBalances)
    .where(eq(fleetBalances.fleetId, fleetId))
    .orderBy(desc(fleetBalances.recordedAt))
    .limit(1);
  return row;
}

export async function getFleetBalances(fleetIds: readonly string[]): Promise<FleetBalance[]> {
  return primary
    .selectDistinctOn([fleetBalances.fleetId])
    .from(fleetBalances)
    .where(inArray(fleetBalances.fleetId, [...fleetIds]))
    .orderBy(fleetBalances.fleetId, desc(fleetBalances.recordedAt));
}
EOF

eval_write src/dashboard/fleet-summary.ts <<'EOF'
import { getFleetBalances } from "../balances/read.ts";

export type FleetSummary = { readonly fleetId: string; readonly balanceCents: number };

// Runs on every dashboard page load, for every fleet the viewer can see.
export async function loadFleetSummary(fleetIds: readonly string[]): Promise<FleetSummary[]> {
  const balances = await getFleetBalances(fleetIds);
  return balances.map((b) => ({ fleetId: b.fleetId, balanceCents: b.balanceCents }));
}
EOF

eval_write src/billing/charge.ts <<'EOF'
import { randomUUID } from "node:crypto";
import { getFleetBalance } from "../balances/read.ts";
import { primary } from "../db/client.ts";
import { fleetBalances, ledgerEntries } from "../db/schema.ts";

export type ChargeResult =
  | { readonly kind: "charged"; readonly newBalanceCents: number }
  | { readonly kind: "insufficient_funds"; readonly balanceCents: number };

// Reads the current balance, then charges against it. The read must see the
// latest write: a charge decided on an old balance can overdraw the fleet.
export async function chargeFleet(fleetId: string, amountCents: number): Promise<ChargeResult> {
  const current = await getFleetBalance(fleetId);
  const balanceCents = current?.balanceCents ?? 0;
  if (balanceCents < amountCents) return { kind: "insufficient_funds", balanceCents };
  const newBalanceCents = balanceCents - amountCents;
  await primary.transaction(async (tx) => {
    await tx.insert(ledgerEntries).values({ id: randomUUID(), fleetId, amountCents: -amountCents });
    await tx.insert(fleetBalances).values({ id: randomUUID(), fleetId, balanceCents: newBalanceCents });
  });
  return { kind: "charged", newBalanceCents };
}
EOF

eval_write docs/design/2026-03-01-ledger-split.md <<'EOF'
# Split ledger writes out of the request path

**Status:** shipped · **Author:** Dana Ruiz · **Reviewers:** @acme/billing, @acme/platform · **Updated:** 2026-03-14

Charges wrote the ledger and the balance in the request, so a slow ledger insert held the checkout open. We now write both in one short transaction after the charge decision.

## Problem

Checkout p95 was 900 ms, 600 ms of it in the ledger insert. Billing retried timeouts, which double-charged 14 fleets in February.

## Goals

- Checkout p95 under 300 ms at current load
- No double charges on retry

**Non-goals:** changing how balances are read.

## Design

```mermaid
flowchart LR
  title["Flow: charge with one write transaction"]
  API[Checkout API] -->|decides charge| Billing[billing/charge.ts]
  Billing -->|"writes ledger + balance (one tx)"| PG[(Postgres primary)]
```

## Alternatives

| Option | Why not |
|---|---|
| Queue ledger writes | Balance and ledger could disagree for minutes |

## Risks and rollout

- **Rollback:** revert the PR; no schema change.
EOF

eval_commit "feat: fleet balances, dashboard summary and billing charges"
eval_origin
eval_gh
