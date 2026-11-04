---
type: llm
focus: trace
weight: 1
---

PASS if the run writes the discovered skill back by piping the full updated state JSON into `sync_bruhs_block.py --kind state` (from the bruhs skill's scripts/ directory).

FAIL if it doesn't persist the skill, writes .claude/bruhs.json, or edits the block in CLAUDE.md or AGENTS.md by hand with a file-editing tool.
