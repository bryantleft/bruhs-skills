---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it stops when a review pass turns up no new actionable findings, or when an iteration applies no new fixes, without inventing an iteration cap of its own, and ends with a per-iteration summary (findings, what was fixed, declined, pushed) and the final state of PR #42.

FAIL if it does not, or if the run never reached the step this describes.
