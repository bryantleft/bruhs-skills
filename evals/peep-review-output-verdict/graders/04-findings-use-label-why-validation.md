---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: every finding shown to the user starts with a Conventional Comments line `<label> [decoration]: <subject>` (e.g. `issue (blocking): ...`, `suggestion (non-blocking): ...`), has a body saying why it matters, and ends with a one-line validation note naming the probe and its result (e.g. the repro test that fails with 33 vs 32, the query count for a 3-line invoice).

FAIL if it does not, or if the run never reached the step this describes.
