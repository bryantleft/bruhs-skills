---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push; each says which commits the branch now has on top of `main`.

PASS if the last push of feat/b-logic leaves only its own logic commit(s) ("feat(rewards): grant points on purchase") on top of `main`, with neither of #101's original commits ("feat(store): add reward_grants table", the fix commit) replayed on it, consistent with `git rebase --onto origin/main <old-parent-tip> feat/b-logic`. The last push of feat/c-ui likewise has only the logic and UI commits on top of `main`.

FAIL if a final branch still carries #101's original commits (replayed duplicates of the squash), or feat/b-logic was never pushed after the merge.
