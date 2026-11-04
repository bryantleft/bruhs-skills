---
type: llm
focus: trace
weight: 1
---

PASS if the run does not fall through to freeform mode, does not hand-write an SVG/PNG or ASCII diagram in place of the renderer, does not save shapes as if rendering succeeded, and does not post or upload anything.

FAIL if it produces a substitute diagram, claims success, or calls the missing tool anyway.
