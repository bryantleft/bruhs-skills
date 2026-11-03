---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 1 detects the PR for the current branch via `gh pr view --json number,headRefName,url,state,reviewDecision,title`

FAIL if it does not, or if the run never reached the step this describes.
