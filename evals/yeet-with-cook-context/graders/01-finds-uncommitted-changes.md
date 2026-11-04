---
type: llm
focus: trace
weight: 1
---

PASS if the run checks the working tree (git status and git diff, staged and unstaged), finds the uncommitted dark-mode changes (theme.ts, its test, theme-toggle.tsx, settings page.tsx, layout.tsx), and carries on rather than aborting.

FAIL if it never checks for changes, or stops with "no changes to ship".
