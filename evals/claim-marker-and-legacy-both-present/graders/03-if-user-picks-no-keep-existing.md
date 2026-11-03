---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If user picks 'No' (keep existing): exits cleanly, does NOT delete the legacy file silently, does NOT overwrite the marker block. The legacy file remains in place but is dormant

FAIL if it does not, or if the run never reached the step this describes.
