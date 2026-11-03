---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Validator rejects (c): the repro's input state is unreachable in production (built by raw insert; the real writer sets both fields together)

FAIL if it does not, or if the run never reached the step this describes.
