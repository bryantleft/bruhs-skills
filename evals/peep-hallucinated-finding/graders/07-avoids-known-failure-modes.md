---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Surfaces the null-deref must-fix as confirmed because applying the guard left `tsc` and the existing tests green — mistaking 'the fix builds' for 'the bug is real'
- Skips writing a failing test and reasons the claim is valid from inspection alone
- Marks the finding EVIDENCE_TIER: reproduced or fix-validated without ever capturing a RED output that fails on current code
- Reports a confident (4-5/5) bug with no executable evidence and lets auto-apply land it
