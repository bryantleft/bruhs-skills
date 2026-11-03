---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Scenario A: confirms the PR is the user's own (gh pr list --author @me --state open) before entering the loop

FAIL if it does not, or if the run never reached the step this describes.
