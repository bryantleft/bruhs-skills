---
type: llm
focus: trace
weight: 1
---

PASS if the run checks for bruhs config (for example `read_bruhs_block.py --kind state`, or reading CLAUDE.md, AGENTS.md and .claude/bruhs.json), finds none (CLAUDE.md has only hand-written notes), and, because the user already said to skip setup and ship with git, continues in git-only mode without stopping to ask the Config question.

FAIL if it never checks for config, treats CLAUDE.md's notes as bruhs config, stops to ask whether to run /bruhs:claim, or runs claim anyway.
