---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Uses the 8-layer vocabulary exactly. Does NOT invent layer names like 'integration tests' or 'e2e' — those map into 'acceptance specs' or 'unit tests' depending on what they cover

FAIL if it does not, or if the run never reached the step this describes.
