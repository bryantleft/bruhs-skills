---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Uses `git checkout main` instead of `git switch main` despite the command doc explicitly preferring modern git commands
- Force-deletes with `git branch -D` unprompted even though the branch was cleanly merged
- Skips the `git pull` so the user ends up on a stale main
