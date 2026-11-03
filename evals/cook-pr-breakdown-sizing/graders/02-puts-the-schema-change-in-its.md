---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Puts the schema change in its own row (migration plus generated schema only) ahead of the rows that use it

FAIL if it does not, or if the run never reached the step this describes.
