---
type: llm
focus: trace
weight: 1
---

PASS if the candidates are named and described with CONTEXT.md's terms (Subscription, Charge, Customer, Refund) rather than generic names.

FAIL if it proposes things like "BillingService", "PaymentManager", "StripeHandler" or similar generic names.
