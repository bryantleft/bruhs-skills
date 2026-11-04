---
type: llm
focus: trace
weight: 1
---

PASS if both the bruhs:state and bruhs:rules blocks are written, via sync_bruhs_block.py, to both CLAUDE.md and AGENTS.md for code-runner (in code-runner/ or the workspace root).

FAIL if either block is missing from either file, or the files are hand-edited instead of written through the sync helpers.
