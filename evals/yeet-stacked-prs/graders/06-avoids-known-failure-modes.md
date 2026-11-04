---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin and every `gh pr create` and `gh pr edit`, with files, commits and bodies.

PASS if the ledger shows none of the failures below.

FAIL if any of these happens:
- Opens the three PRs all targeting `main`, so each diff includes the layers below
- Puts the migration in the same PR as the code that uses it
- Slices by the existing WIP commits or by file count instead of subject
- Pushes anything to `main`
