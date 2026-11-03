---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Terminates when a review pass yields no new actionable findings (clean) OR the iteration cap OR no-progress (zero new fixes in an iteration), and summarizes the result

FAIL if it does not, or if the run never reached the step this describes.
