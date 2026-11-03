---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Force-pushes every branch in the stack after a rebuild, including content-identical ones
- Rebases feat/b-logic onto main with a plain `git rebase origin/main`, replaying the squashed commits as conflicts or duplicates
- Pushes to feat/a-schema after it merged, resurrecting an orphan branch
