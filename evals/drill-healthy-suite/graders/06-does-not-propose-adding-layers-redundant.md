---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Does NOT propose adding layers redundant with the existing healthy ones — anti-pattern 'leaving old tests when a deeper layer subsumes them' (and its inverse: adding a layer when an existing one already covers the bug class)

FAIL if it does not, or if the run never reached the step this describes.
