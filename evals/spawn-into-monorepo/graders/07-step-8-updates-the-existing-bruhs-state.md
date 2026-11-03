---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 8 updates the existing bruhs:state block in CLAUDE.md and AGENTS.md to add the new framework to stack.frameworks (monorepo uses the frameworks ARRAY form, not framework string) rather than overwriting the existing block

FAIL if it does not, or if the run never reached the step this describes.
