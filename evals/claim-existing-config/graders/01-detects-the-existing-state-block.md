---
type: llm
focus: trace
weight: 1
---

PASS if the run checks for existing config first (read_bruhs_block.py --kind state, or reading CLAUDE.md / AGENTS.md) and recognizes that a bruhs:state block already exists, the one wired to linear-sonner.

FAIL if it misses the block and starts fresh setup, or treats the project as unconfigured.
