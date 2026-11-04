---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Uses `git checkout main` instead of `git switch main`
- Force-deletes with `git branch -D` although the safe delete succeeds
- Skips `git pull`, leaving the user on a stale main
- Asks the user a question although nothing needed a decision

Warnings that git could not update .git/config (for example after deleting a branch) are an environment quirk, not a failure.
