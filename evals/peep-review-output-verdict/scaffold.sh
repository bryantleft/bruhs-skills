#!/usr/bin/env bash
# Billing service. PR #70 (eng-88-invoice-tax, by teammate dana-kim, Closes
# ENG-88) has no comments; the user is on main. The PR body links ENG-88
# (linear-eng mock: three acceptance criteria, the first being "tax is
# rounded once on the subtotal, never per line") and Sentry issue
# BILLING-4F2 (sentry mock). What the review should find in
# src/billing/invoice.ts:
#   - rounding bug (blocking): tax is Math.round()ed per line, so three 105c
#     lines at 10% give 33c tax instead of 32c (a repro fails on current code)
#   - suggestion: buildInvoice looks products up one query per line although
#     db.products.getMany exists (db.queryCount makes a query-count probe easy)
# Filler bait: the branch really is 14 commits behind main, with no conflicts
# and nothing on main that the PR depends on.
# Mid-review push: on the first PR read after its diff has been fetched (or
# the second headRefOid read), origin's eng-88-invoice-tax moves to a new commit by Dana that
# changes the rounding line to Math.floor per line (still wrong: 30c), so a
# head SHA re-fetched before the verdict differs from the one recorded first.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project billing-service hono
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "framework": "Hono", "styling": [], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear", "sentry"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-eng", "team": "ENG", "teamName": "Eng", "project": "billing", "projectName": "Billing"}}
}
JSON
eval_write src/billing/db.ts <<'EOF'
export type Product = { sku: string; name: string; unitPriceCents: number };
export type Order = { id: string; customerId: string; items: { sku: string; quantity: number }[] };

// In-memory store with a query counter, so tests can assert query counts.
export function createDb(products: Product[], orders: Order[]) {
  const bySku = new Map(products.map((p) => [p.sku, p]));
  const byId = new Map(orders.map((o) => [o.id, o]));
  const db = {
    queryCount: 0,
    orders: {
      get(id: string): Order | undefined {
        db.queryCount++;
        return byId.get(id);
      },
    },
    products: {
      get(sku: string): Product | undefined {
        db.queryCount++;
        return bySku.get(sku);
      },
      getMany(skus: string[]): Product[] {
        db.queryCount++;
        return skus.map((s) => bySku.get(s)).filter((p): p is Product => p !== undefined);
      },
    },
  };
  return db;
}
export type Db = ReturnType<typeof createDb>;
EOF
eval_write src/billing/invoice.ts <<'EOF'
import type { Db } from "./db.ts";

export type InvoiceLine = { sku: string; name: string; unitPriceCents: number; quantity: number };

export function subtotalCents(lines: InvoiceLine[]): number {
  return lines.reduce((sum, l) => sum + l.unitPriceCents * l.quantity, 0);
}

export function buildInvoice(db: Db, orderId: string) {
  const order = db.orders.get(orderId);
  if (!order) throw new Error(`order ${orderId} not found`);
  const products = db.products.getMany(order.items.map((i) => i.sku));
  const lines: InvoiceLine[] = order.items.map((item) => {
    const p = products.find((x) => x.sku === item.sku);
    if (!p) throw new Error(`product ${item.sku} not found`);
    return { sku: p.sku, name: p.name, unitPriceCents: p.unitPriceCents, quantity: item.quantity };
  });
  return { orderId, lines, subtotalCents: subtotalCents(lines) };
}
EOF
eval_write src/billing/invoice.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createDb } from "./db.ts";
import { buildInvoice } from "./invoice.ts";

test("builds lines and subtotal", () => {
  const db = createDb([{ sku: "A", name: "Widget", unitPriceCents: 1000 }], [{ id: "o1", customerId: "c1", items: [{ sku: "A", quantity: 2 }] }]);
  assert.equal(buildInvoice(db, "o1").subtotalCents, 2000);
});
EOF
eval_commit "feat(billing): invoices with subtotal"
BRANCH_POINT="$(git rev-parse HEAD)"

# main moves on: 14 unrelated commits the PR neither conflicts with nor needs
for i in $(seq 1 14); do
    eval_write "src/notifications/templates/t$i.ts" <<EOF
export const template$i = { id: "t$i", subject: "Notification $i" };
EOF
    eval_commit "chore(notifications): add template t$i"
done

# --- the PR branch, from before those 14 commits ----------------------------
git switch -q -c eng-88-invoice-tax "$BRANCH_POINT"
export GIT_AUTHOR_NAME="Dana Kim" GIT_AUTHOR_EMAIL="dana@example.com"
eval_write src/billing/invoice.ts <<'EOF'
import type { Db } from "./db.ts";

export type InvoiceLine = { sku: string; name: string; unitPriceCents: number; quantity: number };
export type Invoice = { orderId: string; lines: InvoiceLine[]; subtotalCents: number; taxCents: number; totalCents: number };

export function subtotalCents(lines: InvoiceLine[]): number {
  return lines.reduce((sum, l) => sum + l.unitPriceCents * l.quantity, 0);
}

export function taxCents(lines: InvoiceLine[], taxRate: number): number {
  return lines.reduce((sum, l) => sum + Math.round(l.unitPriceCents * l.quantity * taxRate), 0);
}

export function buildInvoice(db: Db, orderId: string, taxRate: number): Invoice {
  const order = db.orders.get(orderId);
  if (!order) throw new Error(`order ${orderId} not found`);
  const lines: InvoiceLine[] = order.items.map((item) => {
    const p = db.products.get(item.sku);
    if (!p) throw new Error(`product ${item.sku} not found`);
    return { sku: p.sku, name: p.name, unitPriceCents: p.unitPriceCents, quantity: item.quantity };
  });
  const subtotal = subtotalCents(lines);
  const tax = taxCents(lines, taxRate);
  return { orderId, lines, subtotalCents: subtotal, taxCents: tax, totalCents: subtotal + tax };
}
EOF
eval_write src/billing/invoice.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createDb } from "./db.ts";
import { buildInvoice } from "./invoice.ts";

test("adds tax to the subtotal", () => {
  const db = createDb([{ sku: "A", name: "Widget", unitPriceCents: 1000 }], [{ id: "o1", customerId: "c1", items: [{ sku: "A", quantity: 2 }] }]);
  const inv = buildInvoice(db, "o1", 0.1);
  assert.deepEqual([inv.subtotalCents, inv.taxCents, inv.totalCents], [2000, 200, 2200]);
});
EOF
eval_write src/billing/routes.ts <<'EOF'
import type { Db } from "./db.ts";
import { buildInvoice } from "./invoice.ts";

const TAX_RATE = 0.1;

export function getInvoice(db: Db, orderId: string): Response {
  return Response.json(buildInvoice(db, orderId, TAX_RATE));
}
EOF
eval_commit "feat(billing): add sales tax to invoices"

eval_origin

# Dana's follow-up push, parked in origin until the review is under way.
perl -pi -e 's/sum \+ Math\.round\(l\.unitPriceCents \* l\.quantity \* taxRate\)/sum + Math.floor(l.unitPriceCents * l.quantity * taxRate)/' src/billing/invoice.ts
grep -q 'Math.floor' src/billing/invoice.ts || { echo "scaffold: author commit edit did not apply" >&2; exit 1; }
eval_commit "fix(billing): floor per-line tax to match the tax report"
git push -q origin "HEAD:refs/local/author-push"
git reset -q --hard HEAD~1
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL
git switch -q main

eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file on-view-70.sh <<'SH'
# Dana pushes once the review is under way: on the first PR read (other than
# the diff itself) after the diff was fetched, or on the second headRefOid read.
if [ ! -f "$EVAL_DIR/author-pushed" ]; then
    log="$EVAL_DIR/gh-calls.log"
    case "$(tail -n 1 "$log")" in
    "gh pr diff"*) ;;
    *)
        if grep -q '^gh pr diff' "$log" || [ "$(grep -c headRefOid "$log")" -ge 2 ]; then
            git --git-dir="$EVAL_DIR/origin.git" update-ref refs/heads/eng-88-invoice-tax refs/local/author-push
            : > "$EVAL_DIR/author-pushed"
        fi ;;
    esac
fi
SH
eval_gh_file repo.json <<'JSON'
{"name": "billing-service", "nameWithOwner": "acme/billing-service", "owner": {"login": "acme"}, "url": "https://github.com/acme/billing-service", "defaultBranchRef": {"name": "main"}, "description": "Invoices and payments."}
JSON
eval_gh_file pr-70.json <<'JSON'
{
  "number": 70,
  "title": "feat(billing): add sales tax to invoices",
  "body": "## What\n\nInvoices now carry tax and a total. `buildInvoice` takes the tax rate; `/invoices/:id` passes 10%.\n\n## Why\n\nFinance adds tax by hand and the totals drift from the tax report. Ticket: ENG-88. Error tracker: https://acme.sentry.io/issues/4518821/ (BILLING-4F2).\n\n## Test plan\n\n- [x] unit test for subtotal + tax\n\nCloses ENG-88",
  "url": "https://github.com/acme/billing-service/pull/70",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "dana-kim"},
  "headRefName": "eng-88-invoice-tax",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BEHIND",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/billing-service/actions/runs/70/job/1"}
  ],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-03T08:20:00Z"
}
JSON
echo '[]' | eval_gh_file threads-70.json
echo '[]' | eval_gh_file review-comments-70.json
