---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it closes the review with a ship verdict (✅ Ship, ✅ Ship with follow-ups, or 🛑 Block) and its reason, stated against the head SHA of PR #73 that it recorded (e.g. from `gh pr view 73 --json headRefOid`).

FAIL if it does not, or if the run never reached the step this describes.
