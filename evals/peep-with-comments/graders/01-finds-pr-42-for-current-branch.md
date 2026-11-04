---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: with no PR number given, it looks up the PR for the current branch (perdix-140-add-leaderboard) with `gh pr view --json ...` (fields such as number, headRefName, url, state, reviewDecision, title) and identifies it as PR #42.

FAIL if it does not, or if the run never reached the step this describes.
