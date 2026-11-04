---
type: llm
focus: trace
weight: 1
---

PASS if the run says explicitly that pass-through modules with no behavior to hide are not deepening candidates (they are deletion candidates), and gives the deletion test as the reason.

FAIL if it does not make this distinction.
