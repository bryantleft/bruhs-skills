---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 6 runs `git stash list | grep "bruhs:"`, finds nothing, skips the stash-restore prompt

FAIL if it does not, or if the run never reached the step this describes.
