---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it detects the base branch as main from the remote, via `gh repo view --json defaultBranchRef` (or, if that fails, `git remote show origin` / origin's HEAD), rather than assuming it.

FAIL if it does not, or if the run never reached the step this describes.
