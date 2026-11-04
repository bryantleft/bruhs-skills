---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file lists every push and every gh call in order. The entry "#101 squash-merged by alex" marks when the merge happened and says the remote feat/a-schema was deleted.

PASS if, after the merge entry and before the first push of feat/b-logic that follows it, the agent checks #101's state with gh (for example `gh pr view 101 --json state,baseRefName`), and no push of feat/a-schema appears after the merge entry (pushing there would recreate the deleted branch as an orphan).

FAIL if feat/b-logic was pushed after the merge with no gh check of #101 in between, if feat/a-schema shows up as a "new remote branch" after the merge, or if the merge never happened (feat/a-schema was never pushed).
