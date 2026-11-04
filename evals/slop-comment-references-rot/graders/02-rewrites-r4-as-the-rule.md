---
type: llm
focus: trace
weight: 1
---

PASS if, for '// covers R4 from the plan' above the `if (req.program.paused)` check in src/rewards/grant.ts, the run proposes stating the rule itself (for example "a paused program grants nothing") or deleting the comment because the check already says it.

FAIL if it keeps the plan reference, or replaces it with a link or pointer to the plan, ticket or doc.
