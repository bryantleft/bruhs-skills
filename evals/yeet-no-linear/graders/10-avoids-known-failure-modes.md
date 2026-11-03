---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Fabricates a fake Linear ticket ID like 'PROJ-1' to put into the commit body
- Abandons the whole flow because Linear isn't configured, instead of offering git-only mode
- Produces a non-Conventional-Commits title like 'Add leaderboard' (missing the `feat:` prefix)
