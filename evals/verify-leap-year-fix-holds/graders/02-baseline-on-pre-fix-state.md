---
type: llm
focus: trace
weight: 1
---

PASS if the agent runs its harness against the pre-fix code (the parent commit HEAD~1, or the merge-base with main, e.g. via a detached checkout, a worktree, or `git show HEAD~1:src/dates.ts` into a temp file) and shows that parseDate("2000-02-29") throws a RangeError there.

FAIL if there is no baseline run on the old code, or the "baseline" is reasoning about the diff instead of executed output.
