---
type: llm
focus: trace
weight: 1
---

PASS if the write updates the bruhs:state block in both CLAUDE.md and AGENTS.md with the same content (sync_bruhs_block.py's default; the run may confirm it by reading the block back).

FAIL if only one of the two files gets the new skill, for example by passing `--files CLAUDE.md`.
