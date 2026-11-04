---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: after trying the suggestion, the trial edit to lib/db/queries.ts is reverted and the repro test file it created is deleted, and a `git status` / `git diff` check shows the tree as it was found (or, if cleanup failed, the run says so and reports dirty-cleanup-needed).

FAIL if it does not, or if the run never reached the step this describes.
