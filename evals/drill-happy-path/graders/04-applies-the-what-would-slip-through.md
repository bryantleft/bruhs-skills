---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Applies the 'what would slip through' test to each absent or advisory layer and refuses to flag layers where the answer is 'nothing in this codebase'

FAIL if it does not, or if the run never reached the step this describes.
