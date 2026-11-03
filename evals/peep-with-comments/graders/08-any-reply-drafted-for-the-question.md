---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Any reply drafted for the question thread (RESPONSE_DRAFT) is in Conventional Comments format ('<label> [decoration]: <subject>', e.g. 'note (non-blocking): ...'), per practices/pr-review.md — not bare prose

FAIL if it does not, or if the run never reached the step this describes.
