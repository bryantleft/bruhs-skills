---
type: llm
focus: trace
weight: 1
---

PASS if Step 0 checks for bruhs config (read_bruhs_block.py, or reading CLAUDE.md, AGENTS.md and .claude/bruhs.json) and concludes there is none, even though a hand-written CLAUDE.md exists: it has no bruhs:state block, and there is no AGENTS.md or legacy .claude/bruhs.json.

FAIL if it treats the hand-written CLAUDE.md as config, errors out on the empty or failed read, or never checks.
