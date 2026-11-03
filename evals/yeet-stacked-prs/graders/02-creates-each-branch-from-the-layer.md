---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Creates each branch from the layer below and opens each PR with --base set to the parent branch (bottom PR targets main)

FAIL if it does not, or if the run never reached the step this describes.
