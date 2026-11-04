---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every `gh pr create` and `gh pr edit` with each PR's head and base branch.

PASS if the schema PR's base is `main`, the logic PR's base is the schema PR's branch, and the UI PR's base is the logic PR's branch, and each branch was pushed as new from the layer below (its push entry adds only that layer's commits).

FAIL if any upper PR targets `main`, so its diff includes the layers below, or a branch carries another layer's commits as its own.
