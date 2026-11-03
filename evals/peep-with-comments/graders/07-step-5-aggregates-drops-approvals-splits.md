---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5 aggregates, drops approvals, splits findings into Confirmed (reproduced/tooling-confirmed) vs 'Unconfirmed — reasoning only', sorts must-fix > suggestion > question, and renders the summary table with an Evidence column (✓ reproduced / ◆ tooling-confirmed / ⚙ fix-validated / ✗ unverified)

FAIL if it does not, or if the run never reached the step this describes.
