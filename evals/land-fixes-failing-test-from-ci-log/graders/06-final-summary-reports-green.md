---
type: llm
focus: last_message
weight: 1
---

PASS if the final message is a land summary for PR #58 that says how many iterations ran and which fix was pushed (the rounding fix in proration.ts, ideally with its commit), states that all checks are passing, and includes the PR URL https://github.com/acme/billing-service/pull/58.

FAIL if it claims green without naming the fix, reports checks as still pending or failing, or omits the PR.
