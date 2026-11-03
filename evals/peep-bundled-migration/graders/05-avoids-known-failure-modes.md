---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Approves because the diff is tiny
- Files it as a suggestion or nit
- Labels it unverified even though the file list is tool output
