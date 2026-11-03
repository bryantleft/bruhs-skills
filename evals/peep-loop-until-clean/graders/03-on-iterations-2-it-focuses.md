---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: On iterations >= 2 it focuses on what changed since the last push (plus anything still unresolved), so it converges rather than re-litigating settled code

FAIL if it does not, or if the run never reached the step this describes.
