---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Fabricates 8 deepening candidates that each wrap one utility behind a 'service'-style interface
- Promotes pass-through wrappers to 'modules' that 'need a deeper interface' — exactly the inverse of the deletion test
- Generates 'TextUtils', 'NumberUtils', 'DateUtils' grouping modules where none of the utilities share invariants or ordering — speculative grouping
- Skips the deletion test entirely and lists every file as a candidate
