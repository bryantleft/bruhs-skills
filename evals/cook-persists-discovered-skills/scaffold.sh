#!/usr/bin/env bash
# Next.js + Drizzle storefront with a pricing page and no payments yet.
# bruhs:state lists tooling.skills superpowers, shadcn and
# vercel-react-best-practices (none of which is installed in a run) and
# Linear on linear-perdix. A stripe-best-practices skill is checked into the
# repo at .claude/skills/stripe-best-practices/SKILL.md but is not in
# tooling.skills: that is the skill a run can discover offline. CLAUDE.md and
# AGENTS.md each carry hand-written notes outside the bruhs blocks, which a
# write-back must leave alone.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project storefront next react react-dom drizzle-orm stripe tailwindcss

eval_write CLAUDE.md <<'EOF'
# storefront

House rules (hand-written):
- Prices are integers in cents; never floats.
- Project skills are checked in under .claude/skills/.
EOF
eval_write AGENTS.md <<'EOF'
# storefront — agent notes

- Run `npm test` before you say something works.
- Don't touch drizzle/ migrations by hand.
EOF
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": "nextjs", "styling": ["Tailwind CSS"], "database": ["drizzle"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": ["superpowers", "shadcn", "vercel-react-best-practices"]},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "storefront", "projectName": "Storefront"}}
}
JSON

eval_write .claude/skills/stripe-best-practices/SKILL.md <<'EOF'
---
name: stripe-best-practices
description: Guidance for Stripe integrations: Checkout Sessions vs PaymentIntents, webhooks, idempotency keys, and test-mode keys. Use when adding or changing any Stripe payment, checkout, or subscription flow.
---

# Stripe best practices

- Prefer Checkout Sessions for hosted checkout; create them on the server only.
- Never trust the success redirect: fulfil orders from the `checkout.session.completed` webhook, verified with the endpoint's signing secret.
- Send an idempotency key on every create call that a retry could repeat.
- Keep the secret key server-side; only the publishable key reaches the browser.
EOF

eval_write src/lib/plans.ts <<'EOF'
export type Plan = { readonly id: "starter" | "pro"; readonly name: string; readonly priceCents: number };

export const plans: readonly Plan[] = [
  { id: "starter", name: "Starter", priceCents: 900 },
  { id: "pro", name: "Pro", priceCents: 2900 },
];

export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
EOF

eval_write src/lib/plans.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatPrice } from "./plans.ts";

test("formats cents", () => {
  assert.equal(formatPrice(2900), "$29.00");
});
EOF

eval_write src/app/pricing/page.tsx <<'EOF'
import { formatPrice, plans } from "../../lib/plans";

export default function PricingPage() {
  return (
    <main className="mx-auto grid max-w-3xl gap-4 p-6 md:grid-cols-2">
      {plans.map((p) => (
        <section key={p.id} className="rounded-lg border p-4">
          <h2 className="font-semibold">{p.name}</h2>
          <p>{formatPrice(p.priceCents)} / month</p>
          <button type="button" className="mt-4 rounded bg-black px-3 py-2 text-white" disabled>
            Coming soon
          </button>
        </section>
      ))}
    </main>
  );
}
EOF

eval_write src/db/schema.ts <<'EOF'
import { pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull().unique(),
  plan: text("plan"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});
EOF

eval_commit "feat: pricing page"
eval_origin
eval_gh
