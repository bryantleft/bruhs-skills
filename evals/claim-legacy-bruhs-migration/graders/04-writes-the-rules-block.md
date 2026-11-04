---
type: llm
focus: trace
weight: 1
---

PASS if the run also writes a bruhs:rules block derived from the legacy JSON (derive_stack_rules.py piped into sync_bruhs_block.py --kind rules, or equivalent), so both a bruhs:state and a bruhs:rules block end up in CLAUDE.md.

FAIL if only the state block is written.
