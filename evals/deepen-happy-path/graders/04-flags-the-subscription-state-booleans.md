---
type: llm
focus: trace
weight: 1
---

PASS if the run identifies the three state booleans on Subscription (isActive, isPastDue, isCanceled) as friction: callers in upgrade.ts, renewals.ts and retry-failed.ts each set them by hand, so the lifecycle rule (active / past due / canceled) is scattered and impossible combinations are representable. Naming it "boolean-flag interface", "scattered invariants" or both is fine.

FAIL if the booleans and the callers that flip them are not mentioned.
