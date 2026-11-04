---
type: llm
focus: trace
weight: 1
---

PASS if, up to the end of the run (which ends at the reconfigure question), CLAUDE.md and AGENTS.md are not modified: no sync_bruhs_block.py write, no Edit/Write to either file, and no .claude/bruhs.json created.

FAIL if either file is written or edited before the user answers.
