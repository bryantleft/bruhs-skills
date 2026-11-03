---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Never silently treats the legacy file's stack values as authoritative when the marker block exists — the marker block always wins on conflicts

FAIL if it does not, or if the run never reached the step this describes.
