---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats the flag as a complete rollback plan without describing post-launch disable
- Omits tenant scoping for the new audience
- Files CSV export as a deferral with no decision
