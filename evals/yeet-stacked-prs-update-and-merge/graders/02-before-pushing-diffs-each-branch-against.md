---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Before pushing, diffs each branch against its origin tip and pushes only branches whose content changed, using --force-with-lease

FAIL if it does not, or if the run never reached the step this describes.
