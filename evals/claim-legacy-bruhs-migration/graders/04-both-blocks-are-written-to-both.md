---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Both blocks are written to BOTH CLAUDE.md and AGENTS.md — AGENTS.md is created if missing, with a minimal header. The two files end up with identical block contents (mirrored)

FAIL if it does not, or if the run never reached the step this describes.
