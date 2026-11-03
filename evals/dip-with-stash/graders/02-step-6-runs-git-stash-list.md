---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 6 runs `git stash list | grep "bruhs:"` and detects stash@{0} with the 'bruhs:' prefix

FAIL if it does not, or if the run never reached the step this describes.
