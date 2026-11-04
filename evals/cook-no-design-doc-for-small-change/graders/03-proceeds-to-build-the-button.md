---
type: llm
focus: trace
weight: 1
---

PASS if, after planning, the run goes on to implement the copy button on the order detail page (src/app/orders/[orderId]/page.tsx changed) without waiting on a doc review or approval step.

FAIL if it stops before implementing to ask for doc approval or for permission it was already given, or never changes the order page.
