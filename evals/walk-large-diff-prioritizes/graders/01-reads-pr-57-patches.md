---
type: llm
focus: trace
weight: 1
---

PASS if the agent fetches PR #57's metadata and its per-file patches (the pulls/57/files API, `gh pr diff 57`, or `git diff main...feat/upstream-retries`) and inspects the content of src/lib/retryClient.ts and src/lib/http.ts before writing the walkthrough.

FAIL if it writes the walkthrough from the PR title, body or file list alone, or walks a different PR.
