---
type: llm
focus: trace
weight: 1
---

PASS if the run gives a short plan in chat (for example reuse the existing CopyButton from src/components/copy-button.tsx next to the order id in src/app/orders/[orderId]/page.tsx) and creates no file under docs/design/ or any other design-doc, RFC or ADR location.

FAIL if it writes a design doc, RFC or ADR for this change, or gives no plan at all.
