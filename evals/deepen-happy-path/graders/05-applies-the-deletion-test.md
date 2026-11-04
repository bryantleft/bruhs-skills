---
type: llm
focus: trace
weight: 1
---

PASS if the run applies the deletion test explicitly to the modules it considers: it names the module and says where the complexity would go if it were deleted (for example "delete charge.ts and the complexity vanishes: callers call Stripe directly" versus "delete money.ts and zero-decimal handling scatters across 5 callers").

FAIL if it never states the deletion test outcome for a named module.
