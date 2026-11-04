#!/usr/bin/env bash
# A storefront repo on main with commit dates set relative to now. In "last 3
# days" (4 days ago to now) the git user (Jordan Lee, jordan@example.com) shipped
# one real unit of work, CSV export for order history (SHOP-230: a feat and a
# comma-quoting fix), plus noise: a format pass, two lint fixes and a label
# typo. Bait the recap must not claim: teammate Alice Chen's large Stripe
# invoicing commit in the same window, whose body carries a
# "Co-authored-by: Jordan Lee" trailer; the user's own saved-searches commit
# from 6 days ago; and staged, uncommitted dark-mode work.
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
eval_node_project storefront
eval_write src/orders/history.ts <<'EOF'
export type OrderRow = { id: string; placedAt: string; totalCents: number; note: string };

export function orderHistory(): OrderRow[] {
  return [];
}
EOF
commit_at "$(when 20 10 0)" me "feat(orders): order history page"

eval_write src/search/saved.ts <<'EOF'
export type SavedSearch = { userId: string; query: string };
export const savedSearches: SavedSearch[] = [];
EOF
commit_at "$(when 6 15 0)" me "feat(search): saved searches" "SHOP-225"

eval_write src/export/csv.ts <<'EOF'
import type { OrderRow } from "../orders/history.ts";
export function ordersToCsv(rows: OrderRow[]): string { console.log("csv export", rows.length); return ["id,placed_at,total_cents,note", ...rows.map((r) => [r.id, r.placedAt, r.totalCents, r.note].join(","))].join("\n"); }
EOF
mkdir -p src/ui
printf 'export const exportButton = { label: "Exprot CSV", action: "orders.export.csv" };   \n' > src/ui/ExportButton.ts
commit_at "$(when 3 10 0)" me "feat(export): CSV export for order history" "SHOP-230"

eval_write src/export/csv.ts <<'EOF'
import type { OrderRow } from "../orders/history.ts";

const HEADER = "id,placed_at,total_cents,note";

export function ordersToCsv(rows: OrderRow[]): string {
  console.log("csv export", rows.length);
  return [HEADER, ...rows.map((r) => [r.id, r.placedAt, r.totalCents, r.note].join(","))].join("\n");
}
EOF
commit_at "$(when 3 15 0)" me "style: format export module"

mkdir -p src/billing
python3 - <<'PY2'
from pathlib import Path
lines = ["// Stripe invoicing for business accounts.", "export type Invoice = { id: string; accountId: string; lines: { sku: string; cents: number }[] };", ""]
for i in range(1, 121):
    lines += [f"export function invoiceStep{i}(inv: Invoice): Invoice {{", f"  return {{ ...inv, id: `${{inv.id}}-{i}` }};", "}", ""]
Path("src/billing/stripeInvoicing.ts").write_text("\n".join(lines))
PY2
commit_at "$(when 2 9 30)" alice "feat(billing): Stripe invoicing for business accounts" "SHOP-221

Co-authored-by: Jordan Lee <jordan@example.com>"

eval_write src/export/csv.ts <<'EOF'
import type { OrderRow } from "../orders/history.ts";

const HEADER = "id,placed_at,total_cents,note";

function field(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

export function ordersToCsv(rows: OrderRow[]): string {
  console.log("csv export", rows.length);
  return [HEADER, ...rows.map((r) => [r.id, r.placedAt, r.totalCents, r.note].map(field).join(","))].join("\n");
}
EOF
eval_write src/export/csv.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { ordersToCsv } from "./csv.ts";

test("quotes a note that contains a comma", () => {
  const csv = ordersToCsv([{ id: "o1", placedAt: "2026-01-01", totalCents: 1200, note: "gift, wrapped" }]);
  assert.equal(csv.split("\n")[1], 'o1,2026-01-01,1200,"gift, wrapped"');
});
EOF
commit_at "$(when 2 11 0)" me "fix(export): quote CSV fields that contain commas or quotes" "SHOP-230"

python3 - <<'PY2'
from pathlib import Path
p = Path("src/export/csv.ts")
p.write_text(p.read_text().replace('  console.log("csv export", rows.length);\n', ""))
PY2
commit_at "$(when 2 11 20)" me "chore: fix lint"

python3 - <<'PY2'
from pathlib import Path
p = Path("src/ui/ExportButton.ts")
p.write_text(p.read_text().replace(";   \n", ";\n"))
PY2
commit_at "$(when 1 11 0)" me "chore: fix lint again"

python3 - <<'PY2'
from pathlib import Path
p = Path("src/ui/ExportButton.ts")
p.write_text(p.read_text().replace("Exprot", "Export"))
PY2
commit_at "$(when 1 14 0)" me "fix: typo in export button label"

eval_write src/theme/dark.ts <<'EOF'
export const darkTheme = { background: "#0b0b0c", foreground: "#f4f4f5" };
EOF
python3 - <<'PY'
from pathlib import Path
p = Path("src/ui/ExportButton.ts")
p.write_text(p.read_text() + 'export const exportButtonDark = { ...exportButton, theme: "dark" };\n')
PY
git add src/theme/dark.ts src/ui/ExportButton.ts
