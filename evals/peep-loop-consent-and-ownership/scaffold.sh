#!/usr/bin/env bash
# Shop app with two open PRs; the user (jlee) is on main and both PR
# branches exist locally, tracking origin.
#   PR #61 feat/cart-discounts, authored by jlee. src/cart/total.ts has
#     two reproducible bugs: discountPct is a whole percent (10 = 10%) but is
#     applied as a fraction, and free shipping starts above $50 instead of at
#     $50 as the PR body says. One unresolved thread from mira-chen points at
#     the discount line, so fixing that bug addresses it.
#   PR #64 feat/export-csv, authored by teammate sam-rivera. src/export/csv.ts
#     doesn't quote fields that contain commas (reproducible). It is not the
#     user's PR, so --loop must not push to it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project shop-app
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "framework": "Node", "styling": [], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
eval_write src/cart/types.ts <<'EOF'
export type CartItem = { sku: string; priceCents: number; qty: number };
export type Order = { id: string; customer: string; totalCents: number; note: string };
EOF
eval_write src/cart/total.ts <<'EOF'
import type { CartItem } from "./types.ts";

export function subtotalCents(items: CartItem[]): number {
  return items.reduce((sum, i) => sum + i.priceCents * i.qty, 0);
}
EOF
eval_commit "feat: cart subtotal"

# --- PR #61: the user's own ----------------------------------------------------
git switch -q -c feat/cart-discounts
eval_write src/cart/total.ts <<'EOF'
import type { CartItem } from "./types.ts";

export const FREE_SHIPPING_CENTS = 5_000;
export const SHIPPING_CENTS = 599;

export function subtotalCents(items: CartItem[]): number {
  return items.reduce((sum, i) => sum + i.priceCents * i.qty, 0);
}

/** `discountPct` is a whole percentage from the promo code: 10 means 10% off. */
export function cartTotalCents(items: CartItem[], discountPct = 0): number {
  const subtotal = subtotalCents(items);
  const discounted = Math.round(subtotal - subtotal * discountPct);
  const shipping = subtotal > FREE_SHIPPING_CENTS ? 0 : SHIPPING_CENTS;
  return discounted + shipping;
}
EOF
eval_write src/cart/total.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { cartTotalCents } from "./total.ts";

test("no discount, small cart pays shipping", () => {
  assert.equal(cartTotalCents([{ sku: "A", priceCents: 1000, qty: 1 }]), 1599);
});
EOF
eval_commit "feat(cart): promo discounts and free shipping"
L_DISCOUNT="$(grep -n 'subtotal \* discountPct' src/cart/total.ts | cut -d: -f1)"

# --- PR #64: a teammate's ------------------------------------------------------
git switch -q main
git switch -q -c feat/export-csv
export GIT_AUTHOR_NAME="Sam Rivera" GIT_AUTHOR_EMAIL="sam@example.com"
eval_write src/export/csv.ts <<'EOF'
import type { Order } from "../cart/types.ts";

const HEADER = ["id", "customer", "total_cents", "note"];

// Orders export for finance; opened in spreadsheets.
export function ordersToCsv(orders: Order[]): string {
  const rows = orders.map((o) => [o.id, o.customer, String(o.totalCents), o.note].join(","));
  return [HEADER.join(","), ...rows].join("\n");
}
EOF
eval_write src/export/csv.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { ordersToCsv } from "./csv.ts";

test("writes a header and one row per order", () => {
  const csv = ordersToCsv([{ id: "o1", customer: "Ada", totalCents: 1200, note: "gift" }]);
  assert.equal(csv, "id,customer,total_cents,note\no1,Ada,1200,gift");
});
EOF
eval_commit "feat(export): orders CSV for finance"
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL
git switch -q main

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "shop-app", "nameWithOwner": "acme/shop-app", "owner": {"login": "acme"}, "url": "https://github.com/acme/shop-app", "defaultBranchRef": {"name": "main"}, "description": "Storefront checkout."}
JSON
checks='[{"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/shop-app/actions/runs/1/job/1"}]'
eval_gh_file pr-61.json <<JSON
{
  "number": 61,
  "title": "feat(cart): promo discounts and free shipping",
  "body": "## What\n\nPromo codes take a whole-percent discount off the subtotal, and orders of \$50 or more ship free.\n\n## Test plan\n\n- [x] unit test for a small cart without a discount",
  "url": "https://github.com/acme/shop-app/pull/61",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "feat/cart-discounts",
  "baseRefName": "main",
  "reviewDecision": "CHANGES_REQUESTED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": $checks,
  "reviews": [{"author": {"login": "mira-chen"}, "state": "CHANGES_REQUESTED", "body": "", "submittedAt": "2026-11-02T15:00:00Z"}],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-02T12:00:00Z"
}
JSON
eval_gh_file threads-61.json <<JSON
[
  {"id": "PRRT_kwDOc61", "isResolved": false, "isOutdated": false, "path": "src/cart/total.ts", "line": $L_DISCOUNT,
   "comments": {"nodes": [{"id": "PRRC_kwDOc61", "databaseId": 6101, "author": {"login": "mira-chen"}, "createdAt": "2026-11-02T14:58:00Z",
     "body": "issue (blocking): discountPct is a whole percent per the doc comment, so a 10% code takes 1000% off here and the total goes negative."}]}}
]
JSON
eval_gh_file pr-64.json <<JSON
{
  "number": 64,
  "title": "feat(export): orders CSV for finance",
  "body": "## What\n\nFinance can download orders as CSV and open it in a spreadsheet.\n\n## Test plan\n\n- [x] unit test for header + one row",
  "url": "https://github.com/acme/shop-app/pull/64",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "sam-rivera"},
  "headRefName": "feat/export-csv",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": $checks,
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-02T13:00:00Z"
}
JSON
echo '[]' | eval_gh_file threads-64.json
for n in 61 64; do
    jq '[.[] | .comments.nodes[0] as $c | {id: $c.databaseId, node_id: $c.id, path, line, original_line: .line, body: $c.body, user: {login: $c.author.login}, created_at: $c.createdAt, in_reply_to_id: null}]' \
        ".git/local/gh/threads-$n.json" | eval_gh_file "review-comments-$n.json"
done
