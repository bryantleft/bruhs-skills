---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every `gh pr create` and every later `gh pr edit`, with full bodies. Judge each PR by its last recorded body.

PASS if each of the three PR bodies opens with its stack position and links to its neighbours by PR number, in the form of `Stack: 2/3, after #101, before #103` (the bottom PR names the one after it, the top PR the one before it).

FAIL if any PR body lacks the stack position, or doesn't link its neighbours by number (for example the first PR was never edited to link the PR above it).
