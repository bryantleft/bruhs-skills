---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: the matching gap in the pre-existing `POST /admin/exports` handler (src/routes/admin/exports.ts, no authorize call) is surfaced as its own second finding or a named follow-up, not used as a reason to excuse the bulk handler.

FAIL if it does not, or if the run never reached the step this describes.
