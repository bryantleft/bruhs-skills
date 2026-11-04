#!/usr/bin/env bash
# Next.js + Drizzle + Stripe app. src/billing has 9 modules:
#   charge.ts, refund.ts   1:1 pass-throughs to stripe.charges/refunds.create
#   subscription.ts        8 fields + 3 booleans (isActive, isPastDue, isCanceled)
#   receipt.ts             formats and emails a receipt
#   invoice.ts             queries the DB, then formats
#   stripe-client.ts, money.ts, dates.ts, idempotency.ts  utilities
# Callers in src/api and src/jobs each build Stripe.ChargeCreateParams by hand
# (amount in minor units, lowercase currency, metadata keys that disagree:
# orderId vs order_id vs subscription), hand-roll idempotency keys (only one
# uses idempotency.ts), and flip the subscription booleans themselves.
# Decoys that earn their keep: money.ts (zero-decimal currencies, used by 5
# modules) and dates.ts (month-end clamping, used by both renewal jobs).
# CONTEXT.md defines Customer, Subscription ("a charge cadence bound to a
# Customer"), Charge, Refund, Invoice, Receipt.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project billing-app next react react-dom drizzle-orm stripe
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "nextjs", "language": "typescript", "database": ["drizzle-postgres"], "payments": ["stripe"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write CONTEXT.md <<'EOF'
# Domain glossary

- **Customer**: a paying account. Has one Stripe customer id.
- **Subscription**: a charge cadence bound to a Customer. It is active, past due
  (the last renewal Charge failed and we are retrying), or canceled.
- **Charge**: one attempt to take money from a Customer. Succeeds or fails.
- **Refund**: money returned against a succeeded Charge, in full or in part.
- **Invoice**: the record of what a Customer owes for one billing period.
- **Receipt**: the email a Customer gets after a succeeded Charge.
EOF

eval_write src/db/schema.ts <<'EOF'
import { boolean, integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const customers = pgTable("customers", {
  id: text("id").primaryKey(),
  email: text("email").notNull(),
  stripeCustomerId: text("stripe_customer_id").notNull(),
});

export const subscriptions = pgTable("subscriptions", {
  id: text("id").primaryKey(),
  customerId: text("customer_id").notNull(),
  plan: text("plan").notNull(),
  amountMinor: integer("amount_minor").notNull(),
  currency: text("currency").notNull(),
  cadence: text("cadence").$type<"monthly" | "yearly">().notNull(),
  currentPeriodEnd: timestamp("current_period_end").notNull(),
  lastChargeId: text("last_charge_id"),
  isActive: boolean("is_active").notNull().default(true),
  isPastDue: boolean("is_past_due").notNull().default(false),
  isCanceled: boolean("is_canceled").notNull().default(false),
});

export const invoices = pgTable("invoices", {
  id: text("id").primaryKey(),
  subscriptionId: text("subscription_id").notNull(),
  amountMinor: integer("amount_minor").notNull(),
  currency: text("currency").notNull(),
  periodEnd: timestamp("period_end").notNull(),
});
EOF

eval_write src/db/client.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";

export const db = drizzle(process.env.DATABASE_URL ?? "");
EOF

eval_write src/billing/stripe-client.ts <<'EOF'
import Stripe from "stripe";

const key = process.env.STRIPE_SECRET_KEY;
if (!key) throw new Error("STRIPE_SECRET_KEY is not set; billing cannot start");

export const stripe = new Stripe(key);
EOF

eval_write src/billing/charge.ts <<'EOF'
import type Stripe from "stripe";
import { stripe } from "./stripe-client";

export async function createCharge(
  params: Stripe.ChargeCreateParams,
  options?: Stripe.RequestOptions,
): Promise<Stripe.Charge> {
  return stripe.charges.create(params, options);
}
EOF

eval_write src/billing/refund.ts <<'EOF'
import type Stripe from "stripe";
import { stripe } from "./stripe-client";

export async function createRefund(
  params: Stripe.RefundCreateParams,
  options?: Stripe.RequestOptions,
): Promise<Stripe.Refund> {
  return stripe.refunds.create(params, options);
}
EOF

eval_write src/billing/subscription.ts <<'EOF'
import { eq } from "drizzle-orm";
import { db } from "../db/client";
import { subscriptions } from "../db/schema";

export type Subscription = {
  id: string;
  customerId: string;
  plan: string;
  amountMinor: number;
  currency: string;
  cadence: "monthly" | "yearly";
  currentPeriodEnd: Date;
  lastChargeId: string | null;
  isActive: boolean;
  isPastDue: boolean;
  isCanceled: boolean;
};

export async function getSubscription(id: string): Promise<Subscription | undefined> {
  const [row] = await db.select().from(subscriptions).where(eq(subscriptions.id, id));
  return row;
}

export async function saveSubscription(sub: Subscription): Promise<void> {
  await db.update(subscriptions).set(sub).where(eq(subscriptions.id, sub.id));
}
EOF

eval_write src/billing/money.ts <<'EOF'
// Currencies Stripe charges in whole units (no minor unit).
const ZERO_DECIMAL = new Set(["jpy", "krw", "vnd", "clp"]);

export function toMinorUnits(amount: number, currency: string): number {
  return ZERO_DECIMAL.has(currency.toLowerCase()) ? Math.round(amount) : Math.round(amount * 100);
}

export function formatMoney(amountMinor: number, currency: string): string {
  const code = currency.toUpperCase();
  const major = ZERO_DECIMAL.has(currency.toLowerCase()) ? amountMinor : amountMinor / 100;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: code }).format(major);
}
EOF

eval_write src/billing/dates.ts <<'EOF'
// Next period end. Clamps to the last day of shorter months, so a
// subscription started on Jan 31 renews on Feb 28/29, then Mar 31.
export function nextPeriodEnd(from: Date, cadence: "monthly" | "yearly", anchorDay = from.getUTCDate()): Date {
  const months = cadence === "monthly" ? 1 : 12;
  const year = from.getUTCFullYear();
  const month = from.getUTCMonth() + months;
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return new Date(Date.UTC(year, month, Math.min(anchorDay, lastDay)));
}
EOF

eval_write src/billing/idempotency.ts <<'EOF'
export function idempotencyKey(scope: string, id: string): string {
  return `${scope}:${id}`;
}
EOF

eval_write src/billing/receipt.ts <<'EOF'
import type Stripe from "stripe";
import { formatMoney } from "./money";

export async function sendReceipt(to: string, charge: Stripe.Charge): Promise<void> {
  const body = [
    `Thanks for your payment of ${formatMoney(charge.amount, charge.currency)}.`,
    `Card ending ${charge.payment_method_details?.card?.last4 ?? "????"}.`,
    `Reference: ${charge.id}`,
  ].join("\n");
  const res = await fetch("https://mail.internal/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to, subject: "Your receipt", body }),
  });
  if (!res.ok) throw new Error(`receipt email to ${to} for charge ${charge.id} failed: HTTP ${res.status}`);
}
EOF

eval_write src/billing/invoice.ts <<'EOF'
import { eq } from "drizzle-orm";
import { db } from "../db/client";
import { invoices } from "../db/schema";
import { formatMoney } from "./money";

export async function renderInvoice(invoiceId: string): Promise<string> {
  const [invoice] = await db.select().from(invoices).where(eq(invoices.id, invoiceId));
  if (!invoice) throw new Error(`invoice ${invoiceId} not found`);
  return [
    `Invoice ${invoice.id}`,
    `Period ending ${invoice.periodEnd.toISOString().slice(0, 10)}`,
    `Amount due: ${formatMoney(invoice.amountMinor, invoice.currency)}`,
  ].join("\n");
}
EOF

eval_write src/api/checkout.ts <<'EOF'
import { createCharge } from "../billing/charge";
import { toMinorUnits } from "../billing/money";
import { sendReceipt } from "../billing/receipt";

type Order = { id: string; total: number; currency: string; customer: { email: string; stripeCustomerId: string } };

export async function checkout(order: Order): Promise<{ chargeId: string }> {
  const charge = await createCharge(
    {
      amount: toMinorUnits(order.total, order.currency),
      currency: order.currency.toLowerCase(),
      customer: order.customer.stripeCustomerId,
      metadata: { orderId: order.id },
    },
    { idempotencyKey: `checkout-${order.id}` },
  );
  if (charge.status !== "succeeded") {
    throw new Error(`charge for order ${order.id} ${charge.status}: ${charge.failure_message ?? "no reason given"}`);
  }
  await sendReceipt(order.customer.email, charge);
  return { chargeId: charge.id };
}
EOF

eval_write src/api/upgrade.ts <<'EOF'
import { createCharge } from "../billing/charge";
import { toMinorUnits } from "../billing/money";
import { getSubscription, saveSubscription } from "../billing/subscription";

export async function upgradePlan(subscriptionId: string, plan: string, prorated: number, stripeCustomerId: string) {
  const sub = await getSubscription(subscriptionId);
  if (!sub) throw new Error(`subscription ${subscriptionId} not found`);
  if (sub.isCanceled) throw new Error(`subscription ${subscriptionId} is canceled`);
  const charge = await createCharge(
    {
      amount: toMinorUnits(prorated, sub.currency),
      currency: sub.currency.toLowerCase(),
      customer: stripeCustomerId,
      metadata: { order_id: `upgrade-${subscriptionId}`, plan },
    },
    { idempotencyKey: `${subscriptionId}/${plan}` },
  );
  await saveSubscription({
    ...sub,
    plan,
    lastChargeId: charge.id,
    isActive: charge.status === "succeeded",
    isPastDue: charge.status !== "succeeded",
  });
}
EOF

eval_write src/api/refunds.ts <<'EOF'
import { createRefund } from "../billing/refund";
import { toMinorUnits } from "../billing/money";

export async function refundOrder(chargeId: string, amount: number, currency: string): Promise<string> {
  const refund = await createRefund({ charge: chargeId, amount: toMinorUnits(amount, currency) });
  return refund.id;
}
EOF

eval_write src/jobs/renewals.ts <<'EOF'
import { createCharge } from "../billing/charge";
import { nextPeriodEnd } from "../billing/dates";
import { idempotencyKey } from "../billing/idempotency";
import { saveSubscription, type Subscription } from "../billing/subscription";

export async function renew(sub: Subscription, stripeCustomerId: string): Promise<void> {
  if (!sub.isActive || sub.isCanceled) return;
  const charge = await createCharge(
    {
      amount: sub.amountMinor,
      currency: sub.currency.toLowerCase(),
      customer: stripeCustomerId,
      metadata: { subscription: sub.id },
    },
    { idempotencyKey: idempotencyKey("renewal", `${sub.id}:${sub.currentPeriodEnd.toISOString()}`) },
  );
  if (charge.status === "succeeded") {
    await saveSubscription({ ...sub, lastChargeId: charge.id, isPastDue: false, currentPeriodEnd: nextPeriodEnd(sub.currentPeriodEnd, sub.cadence) });
  } else {
    await saveSubscription({ ...sub, lastChargeId: charge.id, isPastDue: true });
  }
}
EOF

eval_write src/jobs/retry-failed.ts <<'EOF'
import { createCharge } from "../billing/charge";
import { nextPeriodEnd } from "../billing/dates";
import { saveSubscription, type Subscription } from "../billing/subscription";

export async function retryPastDue(sub: Subscription, stripeCustomerId: string, attempt: number): Promise<void> {
  if (!sub.isPastDue) return;
  const charge = await createCharge(
    {
      amount: sub.amountMinor,
      currency: sub.currency,
      customer: stripeCustomerId,
      metadata: { subscriptionId: sub.id, retry: String(attempt) },
    },
    { idempotencyKey: `retry_${sub.id}_${attempt}` },
  );
  if (charge.status === "succeeded") {
    await saveSubscription({ ...sub, lastChargeId: charge.id, isPastDue: false, isActive: true, currentPeriodEnd: nextPeriodEnd(sub.currentPeriodEnd, sub.cadence) });
  } else if (attempt >= 4) {
    await saveSubscription({ ...sub, isActive: false, isCanceled: true });
  }
}
EOF

eval_write src/billing/money.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatMoney, toMinorUnits } from "./money.ts";

test("yen has no minor unit", () => {
  assert.equal(toMinorUnits(1200, "JPY"), 1200);
  assert.equal(formatMoney(1200, "jpy"), "¥1,200");
});

test("dollars convert to cents", () => {
  assert.equal(toMinorUnits(12.5, "usd"), 1250);
});
EOF

eval_write src/billing/dates.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { nextPeriodEnd } from "./dates.ts";

test("Jan 31 renews on the last day of February", () => {
  assert.equal(nextPeriodEnd(new Date(Date.UTC(2026, 0, 31)), "monthly").toISOString().slice(0, 10), "2026-02-28");
});
EOF

eval_commit "feat: subscriptions, renewals and refunds on Stripe"
eval_origin
eval_gh
