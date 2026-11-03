---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Phase 1: reads CONTEXT.md first to anchor domain vocabulary, then traces materially different call paths until the domain and dependency shape stabilizes, not running a static linter

FAIL if it does not, or if the run never reached the step this describes.
