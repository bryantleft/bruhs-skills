---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 3 reads ~/.claude.json and finds zero Linear servers, sets linearAvailable=false, and logs the hint about adding mcp-server-linear

FAIL if it does not, or if the run never reached the step this describes.
