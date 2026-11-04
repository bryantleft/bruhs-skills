---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it commits the applied fixes on perdix-140-add-leaderboard with a Conventional Commits message (e.g. `fix: address PR review feedback`) and pushes the branch.

FAIL if it does not, or if the run never reached the step this describes. A push that succeeds but then reports it could not write upstream tracking config is an environment quirk, not a failure.
