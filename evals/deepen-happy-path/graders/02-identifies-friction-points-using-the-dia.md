---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Identifies friction points using the diagnostic categories from practices/architecture-deepening.md — at minimum 'Pass-through' (charge.ts, refund.ts thin wrappers), 'Leaky implementation' (callers constructing stripe.Charge directly), and 'Boolean-flag interfaces' (subscription.ts multi-boolean state)

FAIL if it does not, or if the run never reached the step this describes.
