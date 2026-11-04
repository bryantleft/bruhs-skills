---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- While updating the lower layer (before #101 merged), force-pushes every branch in the stack, including content-identical ones
- Uses plain `git push --force` instead of `--force-with-lease` for a rewritten branch
- Rebases feat/b-logic onto main with a plain `git rebase origin/main`, replaying #101's squashed commits as conflicts or duplicates
- Pushes to feat/a-schema after it merged, resurrecting an orphan branch
- Merges a PR itself, or pushes to `main`
