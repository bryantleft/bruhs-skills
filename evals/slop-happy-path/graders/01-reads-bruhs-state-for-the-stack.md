---
type: llm
focus: trace
weight: 1
---

PASS if the run reads the project's bruhs:state block (for example with `scripts/read_bruhs_block.py --kind state`, or by reading CLAUDE.md / AGENTS.md) and uses it to learn the stack is Next.js / React.

FAIL if it never reads the project config, or decides the stack only by guessing from file names.
