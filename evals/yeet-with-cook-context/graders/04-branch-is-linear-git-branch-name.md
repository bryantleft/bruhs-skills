---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin with the branch name, and every PR with its head branch.

PASS if the work was pushed to a new branch named exactly `perdix-145-add-dark-mode-toggle-to-settings-page` (PERDIX-145's gitBranchName from Linear), and the PR's head is that branch.

FAIL if the branch name differs in any way (for example `feat/dark-mode`, `perdix-145-dark-mode`, `perdix-200-dark-mode`), or nothing was pushed.
