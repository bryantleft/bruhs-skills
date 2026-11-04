---
type: llm
focus: trace
weight: 1
---

PASS if the run drops the redundant type annotations where inference gives the same type: `welcomeSubject: string` (users.ts), `subtotal: number` and `discount: number` (pricing.ts), and `MAILER_URL: string` (mailer.ts). At least three of the four is a pass.

FAIL if it removes fewer than three, or treats these as needing a prompt.
