---
type: llm
focus: trace
weight: 1
---

PASS if Step 4 checks the working tree (git status) before building, finds it clean, and proceeds without stashing or creating a branch.

FAIL if it stashes, creates a branch, or skips the check.
