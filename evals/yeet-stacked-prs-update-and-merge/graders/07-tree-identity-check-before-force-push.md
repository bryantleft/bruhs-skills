---
type: llm
focus: trace
weight: 1
---

PASS if, after rebasing feat/b-logic onto main and before force-pushing it, the run checks that the branch's own changes survived the rebase: it compares the child's own diff (for example `git diff origin/main...HEAD` against the pre-rebase `git diff <old-parent-tip>..<old-b-tip>`, or the tree-identity guard from yeet) and only pushes when they match.

FAIL if it force-pushes the rebased branch with no such comparison.
