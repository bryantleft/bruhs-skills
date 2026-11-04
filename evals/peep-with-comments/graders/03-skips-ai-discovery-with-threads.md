---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: because unresolved threads exist, it goes straight to analyzing those threads. It does not offer or run the zero-comment AI discovery review (no "AI Review" offer, no reviewer-per-changed-file pass).

FAIL if it does not, or if the run never reached the step this describes.
