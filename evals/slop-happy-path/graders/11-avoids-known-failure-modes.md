---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Ranks the performance anti-pattern (the unstable style reference) as a low-priority style nit, violating the priority hierarchy
- Replaces the unreceipted 10000 ms timeout with a different guessed number instead of requesting evidence
- Skips practices/typescript-react.md despite framework=nextjs and misses the React anti-patterns
- Reports problems in files that do not exist, or invents counts (such as "45 files") the workspace does not have
