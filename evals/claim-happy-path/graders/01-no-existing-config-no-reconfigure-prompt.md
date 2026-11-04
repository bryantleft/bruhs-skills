---
type: llm
focus: trace
weight: 1
---

PASS if the run checks for existing bruhs config (a bruhs:state block in CLAUDE.md / AGENTS.md, or a legacy .claude/bruhs.json), finds none, and goes straight into fresh setup without asking whether to reconfigure or migrate.

FAIL if it skips the check, reports a config that is not there, or asks a reconfigure / migrate question.
