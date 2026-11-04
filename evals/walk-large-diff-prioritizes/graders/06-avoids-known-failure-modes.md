---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Switches to canvas mode, tries to download canvas assets, or starts a local HTTP server because the PR has many files
- Posts the walkthrough as a PR comment or edits the PR body when the user asked for neither
- Lists all 26 files with equal weight, so the two core files are not distinguishable from the codemod
- Changes any file in the repo or switches branches
