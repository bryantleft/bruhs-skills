---
type: llm
focus: trace
weight: 1
---

PASS if the run identifies a leaky implementation: callers in src/api and src/jobs build Stripe.ChargeCreateParams themselves (minor units, lowercase currency, metadata, idempotency keys), and it cites concrete evidence such as the disagreeing metadata keys (orderId / order_id / subscription / subscriptionId), the four hand-rolled idempotency-key formats, or retry-failed.ts not lowercasing the currency.

FAIL if the leak is not mentioned, or is mentioned with no evidence from the callers.
