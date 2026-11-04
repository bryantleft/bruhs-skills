#!/usr/bin/env bash
# Hono orders API (bruhs:state framework=hono) for `slop --fix`.
# Safe, auto-fixable slop: unused imports in 4 files (orders.ts: z, LineItem;
# users.ts: randomUUID; webhooks.ts: Order; pricing.ts: formatCents),
# 3 console.log calls in src/ (orders.ts, users.ts, pricing.ts), and 4
# redundant annotations (welcomeSubject, subtotal, discount, MAILER_URL).
# Needs a prompt: 2 `any` (toOrder's row, the webhook event) and 2 hardcoded
# secrets (MAILER_API_KEY in mailer.ts, the DB password fallback in db.ts).
# Decoys that must survive: `import "./env.ts"` (side-effect import that
# validates env at boot), the `Record<string, Handler>` annotation on an
# empty literal (inference would give {}), and console.log in
# scripts/print-routes.ts (that script's output). Lint fails today because of
# the console.logs; typecheck and tests pass.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project orders-api hono pg-promise zod
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "hono", "language": "typescript", "database": ["postgres"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/types.ts <<'EOF'
export type LineItem = { sku: string; unitCents: number; quantity: number };

export type Order = {
  id: string;
  customerId: string;
  items: LineItem[];
  status: "pending" | "paid" | "shipped";
};
EOF

eval_write src/env.ts <<'EOF'
const port = Number(process.env.PORT ?? "3000");
if (!Number.isInteger(port)) {
  throw new Error(`PORT must be an integer, got ${JSON.stringify(process.env.PORT)}`);
}

export const env = { port };
EOF

eval_write src/index.ts <<'EOF'
import "./env.ts";
import { Hono } from "hono";
import { orders } from "./routes/orders.ts";
import { users } from "./routes/users.ts";
import { webhooks } from "./routes/webhooks.ts";

const app = new Hono();
app.route("/orders", orders);
app.route("/users", users);
app.route("/webhooks", webhooks);

export default app;
EOF

eval_write src/lib/db.ts <<'EOF'
import pgPromise from "pg-promise";

const pgp = pgPromise();

export const db = pgp(process.env.DATABASE_URL ?? "postgres://orders:Hunter2-prod@db.internal:5432/orders");
EOF

eval_write src/lib/money.ts <<'EOF'
export function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
EOF

eval_write src/lib/pricing.ts <<'EOF'
import type { LineItem } from "../types.ts";
import { formatCents } from "./money.ts";

export function orderTotal(items: readonly LineItem[]): number {
  let subtotal: number = 0;
  for (const item of items) {
    subtotal += item.unitCents * item.quantity;
  }
  const discount: number = subtotal >= 10_000 ? Math.round(subtotal * 0.05) : 0;
  console.log("subtotal", subtotal);
  return subtotal - discount;
}
EOF

eval_write src/lib/pricing.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { orderTotal } from "./pricing.ts";

test("orders of $100 or more get 5% off", () => {
  assert.equal(orderTotal([{ sku: "a", unitCents: 5_000, quantity: 2 }]), 9_500);
});

test("smaller orders pay full price", () => {
  assert.equal(orderTotal([{ sku: "a", unitCents: 1_250, quantity: 3 }]), 3_750);
});
EOF

eval_write src/lib/mailer.ts <<'EOF'
const MAILER_API_KEY = "mk_live_4f9a2c7e1b8d6a3f5c0e9b2d7a4f1c8e";
const MAILER_URL: string = "https://api.mailer.example/v1/send";

export async function sendWelcomeEmail(to: string, subject: string): Promise<void> {
  const res = await fetch(MAILER_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${MAILER_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ to, subject, template: "welcome" }),
  });
  if (!res.ok) {
    throw new Error(`mailer rejected the welcome email to ${to}: HTTP ${res.status}`);
  }
}
EOF

eval_write src/routes/orders.ts <<'EOF'
import { Hono } from "hono";
import { z } from "zod";
import { db } from "../lib/db.ts";
import { orderTotal } from "../lib/pricing.ts";
import type { LineItem, Order } from "../types.ts";

export const orders = new Hono();

function toOrder(row: any): Order {
  return { id: row.id, customerId: row.customer_id, items: row.items, status: row.status };
}

orders.get("/:id", async (c) => {
  const row = await db.oneOrNone("select * from orders where id = $1", [c.req.param("id")]);
  if (!row) return c.json({ error: `order ${c.req.param("id")} not found` }, 404);
  console.log("order row", row);
  const order = toOrder(row);
  return c.json({ ...order, totalCents: orderTotal(order.items) });
});
EOF

eval_write src/routes/users.ts <<'EOF'
import { Hono } from "hono";
import { randomUUID } from "node:crypto";
import { db } from "../lib/db.ts";
import { sendWelcomeEmail } from "../lib/mailer.ts";

export const users = new Hono();

users.post("/", async (c) => {
  const body = await c.req.json<{ email: string; name: string }>();
  const welcomeSubject: string = `Welcome, ${body.name}`;
  const user = await db.one(
    "insert into users (email, name) values ($1, $2) returning id, email, name",
    [body.email, body.name],
  );
  await sendWelcomeEmail(user.email, welcomeSubject);
  console.log("created user", user.id);
  return c.json(user, 201);
});
EOF

eval_write src/routes/webhooks.ts <<'EOF'
import { Hono } from "hono";
import { db } from "../lib/db.ts";
import type { Order } from "../types.ts";

type Handler = (payload: Record<string, unknown>) => Promise<void>;

const handlers: Record<string, Handler> = {};
handlers["order.shipped"] = async (payload) => {
  await db.none("update orders set status = 'shipped' where id = $1", [payload.orderId]);
};

export const webhooks = new Hono();

webhooks.post("/carrier", async (c) => {
  const event: any = await c.req.json();
  const handler = handlers[event.type];
  if (!handler) return c.json({ error: `no handler for carrier event ${event.type}` }, 422);
  await handler(event.data);
  return c.body(null, 204);
});
EOF

eval_write scripts/print-routes.ts <<'EOF'
// Prints the API's route table: `node --experimental-strip-types scripts/print-routes.ts`
const routes = [
  ["GET", "/orders/:id"],
  ["POST", "/users"],
  ["POST", "/webhooks/carrier"],
];

for (const [method, path] of routes) {
  console.log(`${method.padEnd(6)} ${path}`);
}
EOF

eval_commit "feat: orders, users and carrier webhook routes"
eval_origin
eval_gh
