---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 1 runs `git status`, `git diff --stat`, and `git diff --cached --stat`, detects no changes

FAIL if it does not, or if the run never reached the step this describes.
