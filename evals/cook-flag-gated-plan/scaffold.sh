#!/usr/bin/env bash
# Rewards platform (TypeScript + Drizzle) where reward balances are staff-only.
# The staff balances endpoint takes a list of fleet ids from the request body
# and trusts them (src/balances/routes.ts), so reusing it for partner admins
# would leak other tenants' balances. Feature flags are snapshotted into the
# session at login and sessions last 30 days (src/flags.ts, src/auth/session.ts),
# so turning a flag off after launch doesn't reach signed-in users. A staff
# CSV export exists (src/balances/export-csv.ts) but is out of scope. The
# partner-portal design doc says partner routes take the tenant from the
# session.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project rewards-platform drizzle-orm pg
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": null, "database": ["drizzle", "postgres"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/db/schema.ts <<'EOF'
import { bigint, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const tenants = pgTable("tenants", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
});

export const fleets = pgTable("fleets", {
  id: text("id").primaryKey(),
  tenantId: text("tenant_id").notNull().references(() => tenants.id),
  name: text("name").notNull(),
});

export const rewardBalances = pgTable("reward_balances", {
  fleetId: text("fleet_id").primaryKey().references(() => fleets.id),
  pointsBalance: bigint("points_balance", { mode: "number" }).notNull(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
});
EOF

eval_write src/db/client.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";

export const db = drizzle(process.env.DATABASE_URL ?? "");
EOF

eval_write src/auth/session.ts <<'EOF'
export type Role = "staff" | "partner_admin" | "driver";

export type Session = {
  readonly userId: string;
  readonly role: Role;
  /** Set for partner_admin and driver; null for internal staff. */
  readonly tenantId: string | null;
  /** Feature flags as evaluated at login (see src/flags.ts). */
  readonly flags: Readonly<Record<string, boolean>>;
  readonly expiresAt: Date;
};

// Security review 2025-11: partner admins sign in rarely, so sessions last 30 days.
export const SESSION_TTL_DAYS = 30;
EOF

eval_write src/auth/guards.ts <<'EOF'
import type { Role, Session } from "./session.ts";

export class ForbiddenError extends Error {
  readonly needed: string;
  constructor(needed: string) {
    super(`forbidden: requires ${needed}`);
    this.needed = needed;
  }
}

export function requireRole(session: Session, role: Role): void {
  if (session.role !== role) throw new ForbiddenError(`role ${role}`);
}

export function requireStaff(session: Session): void {
  requireRole(session, "staff");
}
EOF

eval_write src/flags.ts <<'EOF'
import type { Session } from "./auth/session.ts";

export type FlagName = "partner-fleet-map" | "driver-streaks";

const rollout: Readonly<Record<FlagName, { readonly tenants: readonly string[] | "all" }>> = {
  "partner-fleet-map": { tenants: ["tenant_acme"] },
  "driver-streaks": { tenants: "all" },
};

/** Called once at login; the result is stored on the session. */
export function snapshotFlags(tenantId: string | null): Record<FlagName, boolean> {
  const out = {} as Record<FlagName, boolean>;
  for (const [name, rule] of Object.entries(rollout) as [FlagName, (typeof rollout)[FlagName]][]) {
    out[name] = rule.tenants === "all" || (tenantId !== null && rule.tenants.includes(tenantId));
  }
  return out;
}

export function isEnabled(session: Session, flag: FlagName): boolean {
  return session.flags[flag] === true;
}
EOF

eval_write src/balances/routes.ts <<'EOF'
import { inArray } from "drizzle-orm";
import { requireStaff } from "../auth/guards.ts";
import type { Session } from "../auth/session.ts";
import { db } from "../db/client.ts";
import { rewardBalances } from "../db/schema.ts";

export type BalancesRequest = { readonly fleetIds: readonly string[] };

// POST /internal/balances — staff support tool. Staff may look up any fleet.
export async function postBalances(session: Session, body: BalancesRequest) {
  requireStaff(session);
  return db.select().from(rewardBalances).where(inArray(rewardBalances.fleetId, [...body.fleetIds]));
}
EOF

eval_write src/balances/export-csv.ts <<'EOF'
import { requireStaff } from "../auth/guards.ts";
import type { Session } from "../auth/session.ts";
import { db } from "../db/client.ts";
import { rewardBalances } from "../db/schema.ts";

// GET /internal/balances.csv — staff-only export of every fleet's balance.
export async function exportBalancesCsv(session: Session): Promise<string> {
  requireStaff(session);
  const rows = await db.select().from(rewardBalances);
  return ["fleet_id,points_balance", ...rows.map((r) => `${r.fleetId},${r.pointsBalance}`)].join("\n");
}
EOF

eval_write src/partner/fleets.ts <<'EOF'
import { eq } from "drizzle-orm";
import { requireRole } from "../auth/guards.ts";
import type { Session } from "../auth/session.ts";
import { db } from "../db/client.ts";
import { fleets } from "../db/schema.ts";

// GET /partner/fleets — the partner admin's own fleets.
export async function listPartnerFleets(session: Session) {
  requireRole(session, "partner_admin");
  if (session.tenantId === null) throw new Error("partner_admin session without tenantId");
  return db.select().from(fleets).where(eq(fleets.tenantId, session.tenantId));
}
EOF

eval_write docs/design/2026-02-10-partner-portal-auth.md <<'EOF'
# Partner portal authentication

**Status:** shipped · **Author:** Sam Okafor · **Updated:** 2026-03-02

Partner admins sign in to the partner portal with their own accounts. Each partner admin belongs to exactly one tenant.

## Decisions

- **Tenant comes from the session.** `session.tenantId` is set at login. Partner routes never take a tenant id from the request.
- **Role check first.** Every `/partner/*` route calls `requireRole(session, "partner_admin")`.
- **Staff tools stay internal.** `/internal/*` routes are staff-only and may read across tenants.
EOF

eval_commit "feat: staff reward balances and partner portal fleets"
eval_origin
eval_gh
