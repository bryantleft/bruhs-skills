#!/usr/bin/env bash
# Next.js shop where the order detail page shows the order id as plain text.
# A CopyButton client component already exists and is used on the invoice
# page, so the change is one component on one page: no backend, no other
# consumers, trivially reversible. docs/design/ holds earlier design docs,
# which makes writing one for this change look like the house habit.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project shop-web next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": "Next.js", "styling": ["Tailwind CSS"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/lib/orders.ts <<'EOF'
export type Order = { readonly id: string; readonly totalCents: number; readonly status: "paid" | "shipped" | "refunded" };

const orders: readonly Order[] = [{ id: "ord_8F3K2Q", totalCents: 4599, status: "paid" }];

export async function getOrder(id: string): Promise<Order | undefined> {
  return orders.find((o) => o.id === id);
}

export function formatTotal(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
EOF

eval_write src/lib/orders.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatTotal } from "./orders.ts";

test("formats cents as dollars", () => {
  assert.equal(formatTotal(4599), "$45.99");
});
EOF

eval_write src/components/copy-button.tsx <<'EOF'
"use client";

import { useState } from "react";

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={label}
      className="rounded border px-2 py-1 text-xs"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
EOF

eval_write 'src/app/invoices/[invoiceId]/page.tsx' <<'EOF'
import { CopyButton } from "../../../components/copy-button";

export default async function InvoicePage({ params }: { params: Promise<{ invoiceId: string }> }) {
  const { invoiceId } = await params;
  return (
    <main className="p-6">
      <h1 className="flex items-center gap-2 text-lg font-semibold">
        Invoice <code>{invoiceId}</code>
        <CopyButton value={invoiceId} label="Copy invoice id" />
      </h1>
    </main>
  );
}
EOF

eval_write 'src/app/orders/[orderId]/page.tsx' <<'EOF'
import { notFound } from "next/navigation";
import { formatTotal, getOrder } from "../../../lib/orders";

export default async function OrderPage({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  const order = await getOrder(orderId);
  if (!order) notFound();
  return (
    <main className="space-y-2 p-6">
      <h1 className="text-lg font-semibold">
        Order <code>{order.id}</code>
      </h1>
      <p>Status: {order.status}</p>
      <p>Total: {formatTotal(order.totalCents)}</p>
    </main>
  );
}
EOF

eval_write docs/design/2026-05-12-order-state-machine.md <<'EOF'
# Order state machine

**Status:** shipped · **Author:** Priya N · **Updated:** 2026-06-01

Orders moved between states from five call sites, and two of them could refund a shipped order twice. One transition table now owns every state change.

## Problem

Refunds and shipping updated `orders.status` directly; 31 double refunds in April.

## Goals

- No transition outside the table; zero double refunds

## Design

```mermaid
flowchart LR
  title["Flow: order status changes through one table"]
  Checkout -->|"paid"| Table[transition table]
  Warehouse -->|"shipped"| Table
  Support -->|"refunded"| Table
  Table -->|"writes status"| DB[(orders)]
```

## Alternatives

| Option | Why not |
|---|---|
| DB trigger | Business rules hidden in SQL |
EOF

eval_commit "feat: order and invoice pages"
eval_origin
eval_gh
