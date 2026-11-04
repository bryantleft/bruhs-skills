---
type: llm
focus: trace
weight: 1
---

PASS if the comment in imageTag() ("The registry rejects tags containing '+', so semver build metadata is dropped.") is still there, unchanged, at the end of the run.

FAIL if the run deletes, rewords or moves that comment: the user asked about the ensureSession comment, and this one is a real WHY.
