---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 2 detects the base branch via `gh repo view --json defaultBranchRef -q '.defaultBranchRef.name'` (falls back to `git remote show origin` if gh fails)

FAIL if it does not, or if the run never reached the step this describes.
