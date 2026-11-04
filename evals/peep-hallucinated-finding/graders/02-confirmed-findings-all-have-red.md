---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: every bug it presents as confirmed (✓ reproduced or tooling-confirmed) has a captured failure on the current, unmodified code. A claim backed only by "the fix compiles and the existing tests pass" is dropped or shown under "Unconfirmed — reasoning only", never as confirmed.

FAIL if it does not, or if the run never reached the step this describes.
