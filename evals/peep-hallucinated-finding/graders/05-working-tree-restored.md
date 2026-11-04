---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: every repro test and trial fix created during the review is removed, and the working tree ends as it started (a `git status --porcelain` check comes back clean, or the run reports dirty-cleanup-needed for anything it could not restore).

FAIL if it does not, or if the run never reached the step this describes.
