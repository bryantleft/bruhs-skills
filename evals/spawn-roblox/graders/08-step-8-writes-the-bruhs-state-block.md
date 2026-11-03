---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 8 writes the bruhs:state block to CLAUDE.md and AGENTS.md with framework='Rojo', language='luau', tooling=['selene','stylua','rojo'], and omits the integrations.linear section

FAIL if it does not, or if the run never reached the step this describes.
