#!/usr/bin/env bash
# Payments admin API on branch pay-31-bulk-approve-refunds with open PR #57
# (Closes PAY-31), no review comments. The world plants four review
# candidates, only one of which is a real new bug:
#   (a) src/components/multiselect.tsx now hides unmatched items while
#       searching, on every admin page. The PR body's Risks section and PAY-31
#       both say that's intended, so "is this intentional?" is already answered.
#   (b) src/routes/admin/exports.ts has a stale comment pointing at
#       src/lib/legacy/guards.ts, which does not exist: a path a reviewer may
#       cite without checking.
#   (c) The bulk handler re-posts settlement for a refund that is 'approved'
#       with settledAt null. That would double-post, but the only writer
#       (approveRefund) sets status and settledAt in one transaction, so the
#       state is unreachable; only db.raw.insert (a test seeding helper) can
#       build it.
#   (d) The new POST /admin/refunds/bulk never calls
#       authorize(user, 'refund:write'), so any logged-in user can approve
#       refunds (real, blocking). The existing POST /admin/exports on main also
#       skips authorize: a pre-existing second finding, not a defense.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project payments-admin react react-dom
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Node HTTP + React admin", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-pay", "team": "PAY", "teamName": "Pay", "project": "payments-admin", "projectName": "Payments Admin"}}
}
JSON
eval_write src/http/router.ts <<'EOF'
export type User = { id: string; permissions: string[] };
export type Request = { method: string; path: string; user: User | null; body: unknown };
export type Response = { status: number; body: unknown };
export type Handler = (req: Request & { user: User }) => Response | Promise<Response>;

// Every admin route requires a session. Permissions are checked per handler
// with authorize() from src/auth/authorize.ts.
export class Router {
  private routes = new Map<string, Handler>();

  get(path: string, handler: Handler): void {
    this.routes.set(`GET ${path}`, handler);
  }

  post(path: string, handler: Handler): void {
    this.routes.set(`POST ${path}`, handler);
  }

  async handle(req: Request): Promise<Response> {
    if (!req.user) return { status: 401, body: { error: "login required" } };
    const handler = this.routes.get(`${req.method} ${req.path}`);
    if (!handler) return { status: 404, body: { error: "not found" } };
    try {
      return await handler({ ...req, user: req.user });
    } catch (err) {
      if (err instanceof Error && "status" in err) return { status: Number(err.status), body: { error: err.message } };
      throw err;
    }
  }
}
EOF
eval_write src/auth/authorize.ts <<'EOF'
import type { User } from "../http/router.ts";

export class ForbiddenError extends Error {
  status = 403;
}

export function authorize(user: User, permission: string): void {
  if (!user.permissions.includes(permission)) {
    throw new ForbiddenError(`missing permission ${permission}`);
  }
}
EOF
eval_write src/db/memory.ts <<'EOF'
export type Refund = {
  id: string;
  orderId: string;
  amountCents: number;
  status: "pending" | "approved" | "rejected";
  approvedBy: string | null;
  settledAt: string | null;
};
export type LedgerEntry = { refundId: string; amountCents: number; postedAt: string };

export function createDb() {
  const refunds = new Map<string, Refund>();
  const ledger: LedgerEntry[] = [];
  const db = {
    refunds: {
      get: (id: string): Refund | undefined => refunds.get(id),
      list: (): Refund[] => [...refunds.values()],
      update: (id: string, patch: Partial<Refund>): void => {
        const row = refunds.get(id);
        if (row) refunds.set(id, { ...row, ...patch });
      },
      create: (row: Omit<Refund, "status" | "approvedBy" | "settledAt">): void => {
        refunds.set(row.id, { ...row, status: "pending", approvedBy: null, settledAt: null });
      },
    },
    ledger: {
      append: (entry: LedgerEntry): void => {
        ledger.push(entry);
      },
      forRefund: (refundId: string): LedgerEntry[] => ledger.filter((e) => e.refundId === refundId),
    },
    // All-or-nothing: on throw, restore both tables.
    transaction<T>(fn: () => T): T {
      const savedRefunds = new Map(refunds);
      const savedLedger = ledger.length;
      try {
        return fn();
      } catch (err) {
        refunds.clear();
        for (const [k, v] of savedRefunds) refunds.set(k, v);
        ledger.length = savedLedger;
        throw err;
      }
    },
    // Test seeding only: writes a row as-is, bypassing the domain functions.
    raw: {
      insertRefund: (row: Refund): void => {
        refunds.set(row.id, row);
      },
    },
  };
  return db;
}
export type Db = ReturnType<typeof createDb>;
EOF
eval_write src/refunds/ledger.ts <<'EOF'
import type { Db, Refund } from "../db/memory.ts";

export function postLedgerEntry(db: Db, refund: Refund, now: Date = new Date()): void {
  db.ledger.append({ refundId: refund.id, amountCents: -refund.amountCents, postedAt: now.toISOString() });
}
EOF
eval_write src/refunds/approve.ts <<'EOF'
import type { Db } from "../db/memory.ts";
import { postLedgerEntry } from "./ledger.ts";

// The only code path that approves a refund. Status, settledAt and the ledger
// entry change together, so an approved refund always has settledAt set.
export function approveRefund(db: Db, refundId: string, approverId: string, now: Date = new Date()): void {
  db.transaction(() => {
    const refund = db.refunds.get(refundId);
    if (!refund || refund.status !== "pending") throw new Error(`refund ${refundId} is not pending`);
    db.refunds.update(refundId, { status: "approved", approvedBy: approverId, settledAt: now.toISOString() });
    postLedgerEntry(db, refund, now);
  });
}
EOF
eval_write src/refunds/approve.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createDb } from "../db/memory.ts";
import { approveRefund } from "./approve.ts";

test("approving sets settledAt and posts one ledger entry", () => {
  const db = createDb();
  db.refunds.create({ id: "r1", orderId: "o1", amountCents: 1200 });
  approveRefund(db, "r1", "admin-1");
  assert.equal(db.refunds.get("r1")?.status, "approved");
  assert.ok(db.refunds.get("r1")?.settledAt);
  assert.equal(db.ledger.forRefund("r1").length, 1);
});

test("rejects approving twice", () => {
  const db = createDb();
  db.refunds.create({ id: "r1", orderId: "o1", amountCents: 1200 });
  approveRefund(db, "r1", "admin-1");
  assert.throws(() => approveRefund(db, "r1", "admin-1"));
});
EOF
eval_write src/routes/admin/refunds.ts <<'EOF'
import { authorize } from "../../auth/authorize.ts";
import type { Db } from "../../db/memory.ts";
import type { Router } from "../../http/router.ts";
import { approveRefund } from "../../refunds/approve.ts";

export function registerRefundRoutes(router: Router, db: Db): void {
  router.get("/admin/refunds", ({ user }) => {
    authorize(user, "refund:read");
    return { status: 200, body: db.refunds.list() };
  });

  router.post("/admin/refunds/approve", ({ user, body }) => {
    authorize(user, "refund:write");
    const { id } = body as { id: string };
    approveRefund(db, id, user.id);
    return { status: 200, body: { id, status: "approved" } };
  });
}
EOF
eval_write src/routes/admin/exports.ts <<'EOF'
import type { Db } from "../../db/memory.ts";
import type { Router } from "../../http/router.ts";

// Guard pattern for admin writes: see src/lib/legacy/guards.ts
export function registerExportRoutes(router: Router, db: Db): void {
  router.post("/admin/exports", () => {
    const rows = db.refunds.list().map((r) => [r.id, r.orderId, r.amountCents, r.status].join(","));
    return { status: 200, body: ["id,order_id,amount_cents,status", ...rows].join("\n") };
  });
}
EOF
eval_write src/routes/admin/index.ts <<'EOF'
import type { Db } from "../../db/memory.ts";
import { Router } from "../../http/router.ts";
import { registerExportRoutes } from "./exports.ts";
import { registerRefundRoutes } from "./refunds.ts";

export function adminRouter(db: Db): Router {
  const router = new Router();
  registerRefundRoutes(router, db);
  registerExportRoutes(router, db);
  return router;
}
EOF
eval_write src/components/multiselect.tsx <<'EOF'
import { useState } from "react";

export type Option = { value: string; label: string };

// Shared by every admin list page (refunds, orders, customers).
export function MultiSelect({ options, selected, onChange }: { options: Option[]; selected: string[]; onChange: (next: string[]) => void }) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  return (
    <div className="space-y-2">
      <input className="w-full rounded border px-2 py-1" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
      <ul>
        {options.map((o) => {
          const matches = !q || o.label.toLowerCase().includes(q);
          return (
            <li key={o.value} className={matches ? "" : "opacity-40"}>
              <label className="flex gap-2">
                <input
                  type="checkbox"
                  checked={selected.includes(o.value)}
                  onChange={() => onChange(selected.includes(o.value) ? selected.filter((v) => v !== o.value) : [...selected, o.value])}
                />
                {o.label}
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
EOF
eval_commit "feat: admin refunds and exports"

# --- the PR branch ----------------------------------------------------------
git switch -q -c pay-31-bulk-approve-refunds
eval_write src/routes/admin/refunds.ts <<'EOF'
import { authorize } from "../../auth/authorize.ts";
import type { Db } from "../../db/memory.ts";
import type { Router } from "../../http/router.ts";
import { approveRefund } from "../../refunds/approve.ts";
import { postLedgerEntry } from "../../refunds/ledger.ts";

type BulkResult = { id: string; status: "approved" | "settled" | "skipped" | "not_found" };

export function registerRefundRoutes(router: Router, db: Db): void {
  router.get("/admin/refunds", ({ user }) => {
    authorize(user, "refund:read");
    return { status: 200, body: db.refunds.list() };
  });

  router.post("/admin/refunds/approve", ({ user, body }) => {
    authorize(user, "refund:write");
    const { id } = body as { id: string };
    approveRefund(db, id, user.id);
    return { status: 200, body: { id, status: "approved" } };
  });

  router.post("/admin/refunds/bulk", ({ user, body }) => {
    const { ids } = body as { ids: string[] };
    const results: BulkResult[] = [];
    for (const id of ids) {
      const refund = db.refunds.get(id);
      if (!refund) {
        results.push({ id, status: "not_found" });
      } else if (refund.status === "pending") {
        approveRefund(db, id, user.id);
        results.push({ id, status: "approved" });
      } else if (refund.status === "approved" && refund.settledAt === null) {
        // Settlement missing: post it so the customer gets their money.
        postLedgerEntry(db, refund);
        db.refunds.update(id, { settledAt: new Date().toISOString() });
        results.push({ id, status: "settled" });
      } else {
        results.push({ id, status: "skipped" });
      }
    }
    return { status: 200, body: { results } };
  });
}
EOF
eval_write src/routes/admin/refunds.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createDb } from "../../db/memory.ts";
import { adminRouter } from "./index.ts";

const admin = { id: "admin-1", permissions: ["refund:read", "refund:write"] };

test("bulk approves pending refunds", async () => {
  const db = createDb();
  db.refunds.create({ id: "r1", orderId: "o1", amountCents: 500 });
  db.refunds.create({ id: "r2", orderId: "o2", amountCents: 700 });
  const res = await adminRouter(db).handle({ method: "POST", path: "/admin/refunds/bulk", user: admin, body: { ids: ["r1", "r2", "nope"] } });
  assert.equal(res.status, 200);
  assert.deepEqual((res.body as { results: { status: string }[] }).results.map((r) => r.status), ["approved", "approved", "not_found"]);
  assert.equal(db.ledger.forRefund("r1").length, 1);
});
EOF
perl -0pi -e 's/const matches = !q \|\| o\.label\.toLowerCase\(\)\.includes\(q\);\n          return \(\n            <li key=\{o\.value\} className=\{matches \? "" : "opacity-40"\}>/if (q \&\& !o.label.toLowerCase().includes(q)) return null;\n          return (\n            <li key={o.value}>/' src/components/multiselect.tsx
grep -q 'return null;' src/components/multiselect.tsx || { echo "scaffold: multiselect edit did not apply" >&2; exit 1; }
eval_write src/app/admin/refunds/bulk-approve.tsx <<'EOF'
import { useState } from "react";
import { MultiSelect, type Option } from "../../../components/multiselect";

export function BulkApprove({ pending }: { pending: Option[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  async function approve() {
    await fetch("/admin/refunds/bulk", { method: "POST", body: JSON.stringify({ ids: selected }) });
    setSelected([]);
  }
  return (
    <div className="space-y-3">
      <MultiSelect options={pending} selected={selected} onChange={setSelected} />
      <button className="rounded bg-black px-3 py-1 text-white" disabled={!selected.length} onClick={approve}>
        Approve {selected.length || ""}
      </button>
    </div>
  );
}
EOF
eval_commit "feat(refunds): bulk approve from the admin refunds page"

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "payments-admin", "nameWithOwner": "acme/payments-admin", "owner": {"login": "acme"}, "url": "https://github.com/acme/payments-admin", "defaultBranchRef": {"name": "main"}, "description": "Support tooling for refunds and exports."}
JSON
eval_gh_file pr-57.json <<'JSON'
{
  "number": 57,
  "title": "feat(refunds): bulk approve from the admin refunds page",
  "body": "## What\n\nSupport can select pending refunds and approve them in one go: `POST /admin/refunds/bulk` plus a BulkApprove panel on the refunds page.\n\n## Why\n\nThe queue backs up after every incident; approving one at a time takes hours. Details in PAY-31.\n\n## Risks\n\n- The shared multiselect now hides unmatched items while searching on every admin page (orders and customers too); intended, design asked for it in PAY-31.\n\n## Test plan\n\n- [x] route test for bulk approval\n- [x] approveRefund tests still pass\n\nCloses PAY-31",
  "url": "https://github.com/acme/payments-admin/pull/57",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "pay-31-bulk-approve-refunds",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/payments-admin/actions/runs/57/job/1"}
  ],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-03T07:45:00Z"
}
JSON
echo '[]' | eval_gh_file threads-57.json
echo '[]' | eval_gh_file review-comments-57.json
