#!/usr/bin/env bash
# A storefront repo on main with two weeks of history dated relative to now.
# Inside "last week" (8 days ago to 1 day ago) the git user (Jordan Lee,
# jordan@example.com) has 8 commits: three for SHOP-210 fuzzy search (net-new),
# fix(cart) SHOP-214 and fix(checkout) SHOP-219 (bugfix), a typo fix, a zod
# bump and an orders.ts split (tech debt). Outside the window or not theirs:
# a user commit 12 days ago (SHOP-190 impersonation), one from today
# (SHOP-225 saved searches, excluded because "last week" stops yesterday),
# and two commits by teammate Alice Chen inside the window.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# when DAYS_AGO HOUR MINUTE: local timestamp DAYS_AGO days before today at
# HOUR:MINUTE, so the recap window logic runs against real relative dates.
when() {
    date -v-"$1"d -v"$2"H -v"$3"M -v0S '+%Y-%m-%dT%H:%M:%S' 2>/dev/null \
        || date -d "$(date +%F) $2:$3 $1 days ago" '+%Y-%m-%dT%H:%M:%S'
}

# commit_at TIMESTAMP WHO SUBJECT [BODY]: stage everything and commit it as
# WHO (me = the repo's git user, alice = a teammate) at TIMESTAMP.
commit_at() {
    local ts="$1" who="$2" subject="$3" body="${4:-}" name email
    case "$who" in
        me) name="Jordan Lee"; email="jordan@example.com" ;;
        alice) name="Alice Chen"; email="alice@example.com" ;;
        *) echo "commit_at: unknown author $who" >&2; return 1 ;;
    esac
    git add -A
    local msg=(-m "$subject")
    [ -n "$body" ] && msg+=(-m "$body")
    GIT_AUTHOR_NAME="$name" GIT_AUTHOR_EMAIL="$email" \
    GIT_COMMITTER_NAME="$name" GIT_COMMITTER_EMAIL="$email" \
    GIT_AUTHOR_DATE="$ts" GIT_COMMITTER_DATE="$ts" \
        git commit -q "${msg[@]}"
}

# Backdate eval_repo's root commit so it never lands in a recap window.
backdate_root() {
    local ts; ts="$(when 30 9 0)"
    GIT_COMMITTER_DATE="$ts" git commit -q --amend --no-edit --allow-empty --date "$ts"
}

eval_repo
backdate_root
eval_node_project storefront zod
eval_write src/cart.ts <<'EOF'
export type Line = { sku: string; qty: number; priceCents: number };

export function addItem(lines: Line[], item: Line): Line[] {
  return [...lines.filter((l) => l.sku !== item.sku), item];
}
EOF
eval_write src/orders.ts <<'EOF'
export type Order = { id: string; lines: { sku: string; qty: number }[] };
const orders = new Map<string, Order>();
export const getOrder = (id: string) => orders.get(id);
export const listOrders = () => [...orders.values()];
export const saveOrder = (o: Order) => void orders.set(o.id, o);
export const deleteOrder = (id: string) => void orders.delete(id);
EOF
eval_write src/checkout.ts <<'EOF'
import type { Line } from "./cart.ts";

export function taxCents(lines: Line[], rate: number): number {
  return Math.round(lines.reduce((sum, l) => sum + l.qty * l.priceCents, 0) * rate);
}
EOF
eval_write src/search/index.ts <<'EOF'
export function search(names: string[], q: string): string[] {
  return names.filter((n) => n.includes(q));
}
EOF
commit_at "$(when 20 10 0)" me "feat: storefront cart, orders and checkout"

eval_write src/admin/impersonate.ts <<'EOF'
export function impersonationToken(supportAgentId: string, customerId: string): string {
  return `imp:${supportAgentId}:${customerId}`;
}
EOF
commit_at "$(when 12 10 0)" me "feat(admin): let support impersonate a customer" "SHOP-190"

eval_write src/search/fuzzy.ts <<'EOF'
export function editDistance(a: string, b: string): number {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}

export function fuzzySearch(names: string[], q: string, maxDistance = 2): string[] {
  return names.filter((n) => editDistance(n.toLowerCase(), q.toLowerCase()) <= maxDistance);
}
EOF
commit_at "$(when 7 10 15)" me "feat(search): fuzzy product search" "SHOP-210"

python3 - <<'PY'
from pathlib import Path
p = Path("src/search/fuzzy.ts")
p.write_text(p.read_text().replace(
    "  return names.filter((n) => editDistance(n.toLowerCase(), q.toLowerCase()) <= maxDistance);",
    "  return names\n    .map((n) => ({ n, d: editDistance(n.toLowerCase(), q.toLowerCase()) }))\n    .filter((x) => x.d <= maxDistance)\n    .sort((x, y) => x.d - y.d || x.n.localeCompare(y.n))\n    .map((x) => x.n);"))
PY
commit_at "$(when 6 14 0)" me "feat(search): rank fuzzy matches by edit distance" "SHOP-210"

eval_write src/search/fuzzy.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { fuzzySearch } from "./fuzzy.ts";

test("ranks closer matches first and breaks ties alphabetically", () => {
  assert.deepEqual(fuzzySearch(["mugs", "mug", "rug"], "mug"), ["mug", "mugs", "rug"]);
});
EOF
commit_at "$(when 6 16 30)" me "test(search): cover fuzzy ranking ties" "SHOP-210"

eval_write src/billing/invoicePdf.ts <<'EOF'
export function invoicePdf(invoiceId: string): Uint8Array {
  return new TextEncoder().encode(`%PDF-1.7 invoice ${invoiceId}`);
}
EOF
commit_at "$(when 5 11 0)" alice "feat(billing): export invoices as PDF" "SHOP-212"

eval_write src/cart.ts <<'EOF'
export type Line = { sku: string; qty: number; priceCents: number };

export function addItem(lines: Line[], item: Line): Line[] {
  const existing = lines.find((l) => l.sku === item.sku);
  if (!existing) return [...lines, item];
  return lines.map((l) => (l.sku === item.sku ? { ...l, qty: l.qty + item.qty } : l));
}

export const CART_FULL = "Your cart is ful";
EOF
commit_at "$(when 5 15 0)" me "fix(cart): keep the existing quantity when an item is re-added" "SHOP-214"

python3 - <<'PY'
from pathlib import Path
p = Path("src/cart.ts")
p.write_text(p.read_text().replace("is ful\"", "is full\""))
PY
commit_at "$(when 5 15 20)" me "fix: typo in cart error message"

python3 - <<'PY'
import json
from pathlib import Path
p = Path("package.json")
pkg = json.loads(p.read_text())
pkg["dependencies"]["zod"] = "^3.23.8"
p.write_text(json.dumps(pkg, indent=2) + "\n")
PY
commit_at "$(when 4 9 40)" me "chore(deps): bump zod to 3.23.8"

eval_write src/auth/refresh.ts <<'EOF'
export const shouldRefresh = (expiresAt: number, now: number) => expiresAt - now < 60_000;
EOF
commit_at "$(when 3 13 0)" alice "fix(auth): refresh tokens a minute before expiry"

git rm -q src/orders.ts
eval_write src/orders/queries.ts <<'EOF'
import { orders } from "./store.ts";
export const getOrder = (id: string) => orders.get(id);
export const listOrders = () => [...orders.values()];
EOF
eval_write src/orders/mutations.ts <<'EOF'
import { orders, type Order } from "./store.ts";
export const saveOrder = (o: Order) => void orders.set(o.id, o);
export const deleteOrder = (id: string) => void orders.delete(id);
EOF
eval_write src/orders/store.ts <<'EOF'
export type Order = { id: string; lines: { sku: string; qty: number }[] };
export const orders = new Map<string, Order>();
EOF
commit_at "$(when 3 17 0)" me "refactor(orders): split orders.ts into queries and mutations"

eval_write src/checkout.ts <<'EOF'
import type { Line } from "./cart.ts";

// Tax is rounded per line item, as the tax authority's invoice rules require.
export function taxCents(lines: Line[], rate: number): number {
  return lines.reduce((sum, l) => sum + Math.round(l.qty * l.priceCents * rate), 0);
}
EOF
commit_at "$(when 2 10 30)" me "fix(checkout): round tax per line item, not on the order total" "SHOP-219"

eval_write src/search/saved.ts <<'EOF'
export type SavedSearch = { userId: string; query: string };
export const savedSearches: SavedSearch[] = [];
EOF
commit_at "$(when 0 0 0)" me "feat(search): saved searches" "SHOP-225"
