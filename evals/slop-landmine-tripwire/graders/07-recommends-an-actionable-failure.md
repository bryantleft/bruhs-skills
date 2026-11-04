---
type: llm
focus: trace
weight: 1
---

PASS if the report recommends that failures surface as an actionable error or an explicit, typed degraded result that states what operation failed (the profile batch fetch), the upstream cause, which policy or assumption was violated (timeout, retries exhausted, invalid response), and what the caller or operator can do next.

FAIL if it recommends only "better logging" or "throw an error" without what the failure must say.
