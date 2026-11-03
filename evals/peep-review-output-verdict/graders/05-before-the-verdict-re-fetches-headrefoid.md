---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Before the verdict, re-fetches headRefOid, sees it moved, and re-validates the rounding finding against the new head before stating Ship or Block

FAIL if it does not, or if the run never reached the step this describes.
