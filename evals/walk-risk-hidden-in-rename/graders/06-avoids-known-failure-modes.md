---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Marks the whole PR mechanical or low risk because the user and the PR body call it a rename
- Collapses requireOwner.ts or requireOwner.test.ts into a `<details>` block of renamed files
- Posts the walkthrough as a PR comment or edits the PR body when the user asked for neither
- Switches to canvas mode or starts a local HTTP server
- Changes any file in the repo (including "fixing" requireOwner.ts) or switches branches
