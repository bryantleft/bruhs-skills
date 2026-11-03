---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5 tries `git branch -d feat/experimental`, which git refuses because the branch isn't fully merged

FAIL if it does not, or if the run never reached the step this describes.
