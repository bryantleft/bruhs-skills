---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Does NOT create a branch, does NOT call linear_create_issue, does NOT attempt `git push`, does NOT call `gh pr create`

FAIL if it does not, or if the run never reached the step this describes.
