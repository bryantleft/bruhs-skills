---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5 generates a branch name from type + description: `git switch -c feat/add-leaderboard` (format `<type>/<short-description>`)

FAIL if it does not, or if the run never reached the step this describes.
