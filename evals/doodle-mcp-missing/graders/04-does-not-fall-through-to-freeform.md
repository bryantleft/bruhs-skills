---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Does not fall through to freeform mode or attempt to call the MCP anyway, since pr mode requires a real renderer

FAIL if it does not, or if the run never reached the step this describes.
