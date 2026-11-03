---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Flags the performance anti-patterns (unstable references, N+1) as low-priority style nits instead of high-priority bugs, violating the priority hierarchy
- Runs auto-fix on type changes without prompting, silently altering behavior
- Replaces an unreceipted operational number with a different guessed number instead of requesting evidence
- Skips loading practices/typescript-react.md despite framework=nextjs, missing React-specific anti-patterns
