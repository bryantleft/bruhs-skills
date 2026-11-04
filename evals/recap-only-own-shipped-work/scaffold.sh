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
. "$(cd "$(dirname "$0")" && pwd)/../_lib/recap_dates.sh"

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
