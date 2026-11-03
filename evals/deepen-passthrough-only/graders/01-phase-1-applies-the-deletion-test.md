---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Phase 1: applies the deletion test (deepen.md L89 / practices L73) to each pass-through file and confirms that deleting any of them moves complexity to ONE call site (or zero), not to N — the 'or vanishes' branch of the deletion test

FAIL if it does not, or if the run never reached the step this describes.
