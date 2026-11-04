---
type: llm
focus: trace
weight: 1
---

PASS if the plan states what a partner admin sees and gets when the flag is off: for example no navigation entry, and the partner balances endpoint refusing the request (404 or 403) rather than returning empty balances.

FAIL if the plan says the feature is behind a flag but never says what flag-off looks like for partner admins.
