---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Accepts the flag because it stops errors in production
- Suggests extending the flag to other readers
- Recommends removing the flag without the write-site fix and backfill, turning old ledgers into hard failures
