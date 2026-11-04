---
type: llm
focus: trace
weight: 1
---

PASS if the run resolves PR #61 and reads its full check set with `gh pr checks` before any `--watch`, sees that `e2e` has already failed while typecheck, lint and test pass, and goes straight to diagnosing `e2e`.

FAIL if it starts by watching the checks, or never reads the PR's check set.
