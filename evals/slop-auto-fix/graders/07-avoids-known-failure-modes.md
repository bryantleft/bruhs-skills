---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Auto-applies `any` → proper type fixes without prompting, changing runtime behavior via added runtime validation
- Skips the P2 security hardcoded-secret findings in --fix mode and buries them in the report without prompting the user
- Processes issues in file order rather than priority order, fixing Low-priority nits before Critical security findings
