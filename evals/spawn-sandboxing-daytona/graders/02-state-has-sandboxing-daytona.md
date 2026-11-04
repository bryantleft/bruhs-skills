---
type: llm
focus: trace
weight: 1
---

PASS if the bruhs:state block the run writes has stack.sandboxing as an array containing "Daytona" (e.g. "sandboxing": ["Daytona"]).

FAIL if no state block is written, the "sandboxing" key is missing, or it holds anything other than the selected Daytona option.
