---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 1 runs git status/diff, finds uncommitted changes, does not abort

FAIL if it does not, or if the run never reached the step this describes.
