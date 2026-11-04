---
type: llm
focus: trace
weight: 1
---

PASS if the run identifies src/billing/charge.ts and src/billing/refund.ts as pass-through modules: each forwards 1:1 to stripe.charges.create / stripe.refunds.create and adds no invariant.

FAIL if it does not call out both wrappers as pass-throughs (by that name or by describing the 1:1 forwarding).
