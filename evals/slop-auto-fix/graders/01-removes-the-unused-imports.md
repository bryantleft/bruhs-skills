---
type: llm
focus: trace
weight: 1
---

PASS if the run removes the unused imports without asking first: `z` and `LineItem` in src/routes/orders.ts, `randomUUID` in src/routes/users.ts, `Order` in src/routes/webhooks.ts, and `formatCents` in src/lib/pricing.ts. Missing one of the five is still a pass if the run removes at least four and does not remove any import that is used.

FAIL if it asks before removing them, leaves most of them in place, or removes an import that is still used.
