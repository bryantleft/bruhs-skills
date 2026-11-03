---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 3 runs `git switch main`, Step 4 runs `git pull origin main`

FAIL if it does not, or if the run never reached the step this describes.
