---
type: llm
focus: trace
weight: 1
---

PASS if the agent's harness exercises at least one input where the remainder is less than half the page size (for example 9 items at size 4, 5 at size 4, or 1 at size 4) and runs it against both the pre-fix code (HEAD~1 or the merge-base with main) and HEAD.

FAIL if every input it runs has a remainder of at least half a page (such as 10 at size 4, or 7 at size 4), or if the falsifying input is only reasoned about and never executed.
