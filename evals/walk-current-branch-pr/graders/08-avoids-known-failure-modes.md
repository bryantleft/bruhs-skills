---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Posts the walkthrough as a PR comment or edits the PR body (`gh pr comment`, `gh pr edit`) when the user asked for neither
- Switches to canvas mode, fetches canvas assets, or starts a local HTTP server
- Invents files, line counts or review comments that are not in PR #42
- Lists risk callouts that are generic ("make sure tests pass") with nothing tied to a file in this PR
- Changes any file in the repo or switches branches
