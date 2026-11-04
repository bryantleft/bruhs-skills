---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Fabricates several deepening candidates that each wrap one utility behind a "service"-style interface
- Promotes pass-through wrappers to modules that "need a deeper interface", the inverse of the deletion test
- Skips the deletion test entirely and lists every file as a candidate
