---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it checks the current branch and working tree (on feat/experimental, clean), detects main as the base branch, switches with `git switch main` and pulls with `git pull origin main`.

FAIL if it does not, or if the run never reached the step this describes.
