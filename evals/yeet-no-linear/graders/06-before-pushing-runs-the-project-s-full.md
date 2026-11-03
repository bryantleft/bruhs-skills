---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Before pushing, runs the project's full validation suite (typecheck + lint + test) as the pre-PR gate mentioned in practices/pr-review.md

FAIL if it does not, or if the run never reached the step this describes.
