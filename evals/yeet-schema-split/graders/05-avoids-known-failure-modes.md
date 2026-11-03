---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Ships one PR because the total diff is under 400 lines
- Splits only when the user asks
- Puts grant.ts or its test in the schema PR
