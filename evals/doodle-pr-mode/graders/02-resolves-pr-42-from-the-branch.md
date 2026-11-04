---
type: llm
focus: trace
weight: 1
---

PASS if the run resolves the PR from the current branch with gh (for example `gh pr view` with no number, or `gh pr list --head perdix-140-add-leaderboard`) and identifies it as PR #42.

FAIL if it never resolves a PR, picks a different number, or asks the user which PR.
