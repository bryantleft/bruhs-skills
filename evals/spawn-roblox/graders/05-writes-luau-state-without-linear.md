---
type: llm
focus: trace
weight: 1
---

PASS if the run writes a bruhs:state block (sync_bruhs_block.py or equivalent) to both CLAUDE.md and AGENTS.md for obby-game (in obby-game/ or the workspace root), with stack.framework Rojo, stack.tooling listing Selene, StyLua and Rojo, and no "linear" key in integrations.

FAIL if no state block is written, only one of the two files gets it, the framework or tooling differs, or integrations.linear is present (even with null or empty values).
