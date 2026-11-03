---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 1 runs `git branch --show-current` and `git status`; confirms we are on a feature branch and working tree is clean (no uncommitted-changes prompt)

FAIL if it does not, or if the run never reached the step this describes.
