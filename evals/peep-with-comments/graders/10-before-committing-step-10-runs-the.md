---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Before committing, Step 10 runs the full CI-equivalent suite (typecheck && lint && test) even though each fix individually passed

FAIL if it does not, or if the run never reached the step this describes.
