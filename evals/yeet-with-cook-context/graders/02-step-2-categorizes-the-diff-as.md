---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 2 categorizes the diff as 'feat' (new feature), generates a Conventional Commits title like 'feat: add dark mode toggle to settings page' (under 70 chars) following practices/pr-review.md + _common.md

FAIL if it does not, or if the run never reached the step this describes.
