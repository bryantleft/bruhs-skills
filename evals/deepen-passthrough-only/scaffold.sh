#!/usr/bin/env bash
# TypeScript orders dashboard whose src/utils holds 14 files, none with
# behavior to hide: 11 one-liners over date-fns, String, Math, Array, Set and
# setTimeout, and 3 files that only re-export from lodash-es, clsx and zod.
# Each is imported from at most one place in src/features (sleep, noop and
# identity from none), so deleting any of them moves one line to one call
# site or nowhere. Bait: the three date-fns wrappers (formatDate,
# formatRelative, parseIsoDate) invite an invented "DateUtils" module.
# There is no CONTEXT.md; the domain lives in src/features.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project orders-dashboard react react-dom date-fns lodash-es clsx zod
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "vite", "language": "typescript", "libraries": ["react", "date-fns", "zod"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

w() { eval_write "src/utils/$1"; }
w formatDate.ts <<'EOF'
import { format } from "date-fns";

export const formatDate = (date: Date): string => format(date, "yyyy-MM-dd");
EOF
w formatRelative.ts <<'EOF'
import { formatDistanceToNow } from "date-fns";

export const formatRelative = (date: Date): string => formatDistanceToNow(date, { addSuffix: true });
EOF
w parseIsoDate.ts <<'EOF'
import { parseISO } from "date-fns";

export const parseIsoDate = (value: string): Date => parseISO(value);
EOF
w capitalize.ts <<'EOF'
export const capitalize = (str: string): string => str[0].toUpperCase() + str.slice(1);
EOF
w clamp.ts <<'EOF'
export const clamp = (value: number, min: number, max: number): number => Math.min(Math.max(value, min), max);
EOF
w isEmpty.ts <<'EOF'
export const isEmpty = <T>(items: readonly T[]): boolean => items.length === 0;
EOF
w sleep.ts <<'EOF'
export const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));
EOF
w uniq.ts <<'EOF'
export const uniq = <T>(items: readonly T[]): T[] => [...new Set(items)];
EOF
w sum.ts <<'EOF'
export const sum = (values: readonly number[]): number => values.reduce((total, n) => total + n, 0);
EOF
w noop.ts <<'EOF'
export const noop = (): void => {};
EOF
w identity.ts <<'EOF'
export const identity = <T>(value: T): T => value;
EOF
w lodash.ts <<'EOF'
export { debounce, throttle } from "lodash-es";
EOF
w cn.ts <<'EOF'
export { clsx as cn } from "clsx";
EOF
w schema.ts <<'EOF'
export { z } from "zod";
EOF

eval_write src/features/orders/types.ts <<'EOF'
export type OrderStatus = "pending" | "shipped" | "delivered";

export type Order = {
  id: string;
  customer: string;
  status: OrderStatus;
  placedAt: string;
  lineTotalsCents: number[];
};
EOF

eval_write src/features/orders/orderRow.ts <<'EOF'
import { capitalize } from "../../utils/capitalize";
import { formatDate } from "../../utils/formatDate";
import { parseIsoDate } from "../../utils/parseIsoDate";
import { sum } from "../../utils/sum";
import type { Order } from "./types";

export function orderRow(order: Order): string[] {
  return [
    order.id,
    order.customer,
    capitalize(order.status),
    formatDate(parseIsoDate(order.placedAt)),
    `$${(sum(order.lineTotalsCents) / 100).toFixed(2)}`,
  ];
}
EOF

eval_write src/features/orders/summary.ts <<'EOF'
import { isEmpty } from "../../utils/isEmpty";
import { uniq } from "../../utils/uniq";
import type { Order } from "./types";

export function summarize(orders: readonly Order[]): string {
  if (isEmpty(orders)) return "No orders yet";
  const customers = uniq(orders.map((o) => o.customer));
  return `${orders.length} orders from ${customers.length} customers`;
}
EOF

eval_write src/features/activity/feed.ts <<'EOF'
import { formatRelative } from "../../utils/formatRelative";

export type Activity = { actor: string; action: string; at: Date };

export function activityLine(item: Activity): string {
  return `${item.actor} ${item.action} ${formatRelative(item.at)}`;
}
EOF

eval_write src/features/search/searchBox.ts <<'EOF'
import { clamp } from "../../utils/clamp";
import { cn } from "../../utils/cn";
import { debounce } from "../../utils/lodash";

export function createSearch(onQuery: (q: string) => void, wait: number) {
  const fire = debounce(onQuery, clamp(wait, 0, 1000));
  return {
    input: (value: string) => fire(value.trim()),
    className: (active: boolean) => cn("search", { "search--active": active }),
  };
}
EOF

eval_write src/features/orders/filters.ts <<'EOF'
import { z } from "../../utils/schema";

export const orderFilter = z.object({
  status: z.enum(["pending", "shipped", "delivered"]).optional(),
  customer: z.string().min(1).optional(),
});

export type OrderFilter = z.infer<typeof orderFilter>;
EOF

eval_commit "feat: orders dashboard"
eval_origin
eval_gh
