---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Each iteration: review the diff → fix actionable findings under the reproduction-first evidence bar (Step 4 / Evidence) → resolve → validate (Step 10) → commit 'fix: self-review pass (peep loop iteration N)' → push → re-review the updated diff

FAIL if it does not, or if the run never reached the step this describes.
