---
type: llm
focus: trace
weight: 1
---

PASS if the run removes the three console.log calls in src/ (src/routes/orders.ts, src/routes/users.ts, src/lib/pricing.ts) without asking first.

FAIL if any of the three remain, or it asks permission for these before removing them.
