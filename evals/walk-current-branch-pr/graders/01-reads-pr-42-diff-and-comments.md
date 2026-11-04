---
type: llm
focus: trace
weight: 1
---

PASS if the agent resolves the PR for the current branch as #42 (for example `gh pr view` with no number) and, before writing the walkthrough, reads both the per-file patches (the pulls/42/files API, `gh pr diff`, or `git diff main...feat/api-rate-limit`) and the existing review comments (the pulls/42/comments API or equivalent).

FAIL if it writes the walkthrough without reading the patches, never looks at review comments, or walks a different PR or diff.
