---
type: llm
focus: trace
weight: 1
---

PASS if the run inspects the working tree for both staged and unstaged changes (for example `git status` plus `git diff --stat` and `git diff --cached --stat`) and concludes there is nothing to ship.

FAIL if it never checks for changes, or decides there are changes to ship.
