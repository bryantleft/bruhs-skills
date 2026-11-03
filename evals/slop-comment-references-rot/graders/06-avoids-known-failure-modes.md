---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Leaves ticket/plan IDs in code comments because they look like useful context
- Keeps the subclass because sibling subclasses follow the same pattern
- Deletes the bypass branch's why along with the other comments, or flags it as over-commenting
- Treats a TODO(ENG-123) tracking open work as a rotting reference
