---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 4 runs git status; since working tree is clean, skips stashing

FAIL if it does not, or if the run never reached the step this describes.
