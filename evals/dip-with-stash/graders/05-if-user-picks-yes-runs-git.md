---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If user picks Yes, runs `git stash pop` and reports the restore; if Drop, runs `git stash drop stash@{0}` only after the user explicitly confirms

FAIL if it does not, or if the run never reached the step this describes.
