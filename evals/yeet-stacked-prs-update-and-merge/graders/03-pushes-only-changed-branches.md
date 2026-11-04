---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin; each forced push says whether its tree is identical to or differs from the previous tip. The entry "#101 squash-merged by alex" marks when the merge happened.

PASS if every push made before the merge entry changes content (none says "Tree identical to the previous tip"), so while updating the lower layer no branch was force-pushed as a no-op rewrite. After the merge, a tree-identical forced push of feat/b-logic or feat/c-ui is fine: it drops #101's squashed commits from the history.

FAIL if a push before the merge entry is content-identical to the branch's previous tip, or there are no pushes.
