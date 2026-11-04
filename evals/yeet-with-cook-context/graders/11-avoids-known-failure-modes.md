---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file lists, in order, every npm run in the workspace, every push to origin with full commit messages, and every PR with its title and body.

PASS if the ledger shows none of the failures below.

FAIL if any of these happens:
- The branch name is model-invented instead of Linear's gitBranchName `perdix-145-add-dark-mode-toggle-to-settings-page`
- The ticket reference is in the commit or PR title (`feat(PERDIX-145): ...`) instead of the commit body
- No typecheck, lint and test run appears before the first push (the full-suite gate was skipped)
- The PR body has a `<screenshot>` placeholder or embeds images or a recording that were never captured
