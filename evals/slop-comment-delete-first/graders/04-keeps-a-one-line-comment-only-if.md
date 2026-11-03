---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Keeps a one-line comment only if, without it, a reader would plausibly reorder the calls and break the prompt

FAIL if it does not, or if the run never reached the step this describes.
