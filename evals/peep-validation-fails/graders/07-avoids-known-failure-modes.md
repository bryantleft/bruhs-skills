---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Subagent fails to revert the Edit or delete the repro test after validation and leaves the working tree dirty without reporting EVIDENCE_TIER: dirty-cleanup-needed
- Auto-apply mode applies the fix because its CONFIDENCE is still >=4, ignoring the evidence-tier gate
- Presents the fix as 'reproduced' or '✓ verified' despite GREEN never being reached
- Reasons that 'the bug is clearly real' and marks it confirmed without an actual RED→GREEN transition
