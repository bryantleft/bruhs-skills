---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Shortens the comment to one or two lines without asking whether it is needed
- Moves the comment to a different spot instead of deciding whether it should exist
- Refuses to delete because the user said 'tighten', not 'remove'
