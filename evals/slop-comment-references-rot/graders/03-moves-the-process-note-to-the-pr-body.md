---
type: llm
focus: trace
weight: 1
---

PASS if the run identifies '// every new reward type also needs a row in reward_kinds' as a process note (it applies to every future reward type, not this line) and recommends moving it out of the code into the PR body's deploy or risks section.

FAIL if it keeps it as a code comment, only rewords it, or does not mention it.
