---
type: llm
focus: trace
weight: 1
---

PASS if the run resolves PR #58 for the current branch (for example `gh pr view --json number,url,headRefName,...`) and reads the PR's full check set with `gh pr checks` (the `--json name,bucket,state,workflow,link` form or the plain form) before any `--watch` call, so it sees that `test` has already failed and goes straight to diagnosing it instead of waiting.

FAIL if it starts by watching (`gh pr checks --watch`) or by `gh run list`, or never looks at the PR's checks.
