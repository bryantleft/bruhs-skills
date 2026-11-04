---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Auto-applies `any` to proper-type fixes without prompting, or adds runtime validation that changes behavior
- Skips the P2 hardcoded-secret findings in --fix mode, or buries them in a report without asking the user about them
- Processes issues in file order rather than priority order, fixing low-priority nits before the type and security findings
- Claims lint now passes without running it, or claims checks passed that were never run
