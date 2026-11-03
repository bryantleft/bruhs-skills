---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Runs `gh api .../pulls/42/files` (paginated) to get the changed-file list with status, and `gh pr diff 42` for patch content

FAIL if it does not, or if the run never reached the step this describes.
