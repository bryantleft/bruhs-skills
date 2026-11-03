---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Drops the parent's original commits from feat/b-logic with `git rebase --onto origin/main <old-parent-tip> feat/b-logic`

FAIL if it does not, or if the run never reached the step this describes.
