---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Presents only one gate design
- Ignores the 10-minute CI budget entirely
- Picks a specific tool (for example mutmut) while framing the layer, before any alternatives are designed
- Stops to ask the user questions instead of making the calls, though the user said they could not answer
