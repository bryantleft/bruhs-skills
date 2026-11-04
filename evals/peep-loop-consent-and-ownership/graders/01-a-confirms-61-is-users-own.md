---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: before entering the loop on #61, it confirms the PR is the user's own, for example with `gh pr list --author @me --state open` or by comparing the PR author with the authenticated user (`gh api user`).

FAIL if it does not, or if the run never reached the step this describes.
