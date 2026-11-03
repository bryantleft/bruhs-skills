---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If user selects cook, cook's Step 4 Setup detects the unrelated changes and offers to stash with the 'bruhs: stashed before <feature-name>' message prefix

FAIL if it does not, or if the run never reached the step this describes.
