---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Groups files into modules (workspace member > layer dir > top-level src/ > extension fallback), parses imports old vs new to compute added/removed/preserved edges

FAIL if it does not, or if the run never reached the step this describes.
