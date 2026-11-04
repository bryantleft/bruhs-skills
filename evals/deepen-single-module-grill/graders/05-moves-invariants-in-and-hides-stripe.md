---
type: llm
focus: trace
weight: 1
---

PASS if the recommended design moves the party-size, date and deposit rules into the module so the three callers stop re-implementing them (locality), and replaces the stripePaymentIntentId parameter with a Deposit concept the module owns, so callers no longer see Stripe ids (leverage).

FAIL if the invariants stay in the callers, or the Stripe PaymentIntent id is still part of the interface callers use.
