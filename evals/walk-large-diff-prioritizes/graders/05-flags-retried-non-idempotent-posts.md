---
type: llm
focus: trace
weight: 1
---

PASS if the Risk callouts flag that postJson now goes through retryingFetch, so non-idempotent POSTs are retried, and name createCharge in src/services/payments.ts (or POSTs to payments generally) as able to charge twice after a timeout or 5xx, since no idempotency key is sent.

FAIL if no risk callout addresses POST requests being retried.
