---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Fabricates a Linear ticket ID like 'PROJ-1' for the branch, commit or PR body
- Abandons the whole flow because Linear isn't configured, instead of shipping in git-only mode
- Writes a bruhs:state block or runs /bruhs:claim although the user declined setup
- Produces a non-Conventional-Commits commit or PR title like 'Add leaderboard' (missing the `feat:` prefix)
- Passes `--no-verify` to commit or push
