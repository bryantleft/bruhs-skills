---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it closes with a 🛑 Block verdict that names the missing refund:write authorization on the bulk endpoint as what unblocks it, stated against the PR #57 head SHA it recorded (for example from `gh pr view 57 --json headRefOid`).

FAIL if it does not, or if the run never reached the step this describes.
