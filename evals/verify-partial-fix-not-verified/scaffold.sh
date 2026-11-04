#!/usr/bin/env bash
# A TypeScript list-pagination module. main's pageCount() floors
# total/size, so paginate() drops a partial last page. The checked-out branch
# fix/last-page "fixes" it with Math.round and adds a test for 10 items at
# page size 4, which passes. The claim is still false: Math.round only rounds
# up when the remainder is at least half a page, so 9 items at size 4 still
# give 2 pages (item 9 is lost) on both the parent commit and HEAD, and
# npm test is green on HEAD.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project order-history
eval_write src/paginate.ts <<'EOF'
export function pageCount(total: number, size: number): number {
  if (!Number.isInteger(size) || size <= 0) {
    throw new RangeError(`pageCount: page size must be a positive integer, got ${size}`);
  }
  return Math.floor(total / size);
}

export function paginate<T>(items: readonly T[], size: number): T[][] {
  const pages: T[][] = [];
  const count = pageCount(items.length, size);
  for (let page = 0; page < count; page++) {
    pages.push(items.slice(page * size, (page + 1) * size));
  }
  return pages;
}
EOF
eval_write src/paginate.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { paginate, pageCount } from "./paginate.ts";

const range = (n: number) => Array.from({ length: n }, (_, i) => i + 1);

test("splits an exact multiple into full pages", () => {
  assert.deepEqual(paginate(range(8), 4), [[1, 2, 3, 4], [5, 6, 7, 8]]);
});

test("rejects a zero page size", () => {
  assert.throws(() => pageCount(5, 0), RangeError);
});
EOF
eval_write src/orders.ts <<'EOF'
import { paginate } from "./paginate.ts";

export type Order = { id: string; totalCents: number };

export function orderHistoryPages(orders: readonly Order[], pageSize: number): Order[][] {
  return paginate(orders, pageSize);
}
EOF
eval_commit "feat(orders): paginate order history"

git switch -q -c fix/last-page
python3 - <<'PY'
from pathlib import Path
p = Path("src/paginate.ts")
p.write_text(p.read_text().replace("Math.floor(total / size)", "Math.round(total / size)"))
PY
cat >> src/paginate.test.ts <<'EOF'

test("keeps the partial last page", () => {
  assert.deepEqual(paginate(range(10), 4), [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]]);
});
EOF
git add -A
git commit -q -m "fix(paginate): stop dropping the last partial page" -m "Customers with 10 orders only saw 8 in their order history: pageCount floored total/size, so the partial last page was never emitted."
eval_origin
eval_gh
