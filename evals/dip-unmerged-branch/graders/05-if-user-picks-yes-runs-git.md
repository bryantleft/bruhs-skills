---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If user picks Yes, runs `git branch -D feat/experimental` and also attempts `git push origin --delete feat/experimental`

FAIL if it does not, or if the run never reached the step this describes.
