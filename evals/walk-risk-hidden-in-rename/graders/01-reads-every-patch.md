---
type: llm
focus: trace
weight: 1
---

PASS if the agent reads the actual patch content for PR #63's files, including src/projects/requireOwner.ts and src/projects/requireOwner.test.ts (via the pulls/63/files API, `gh pr diff 63`, or `git diff main...refactor/account-id`), instead of relying on the PR body or the user's "just the accountId rename".

FAIL if it builds the walkthrough from the title, body or file list without reading the patches.
