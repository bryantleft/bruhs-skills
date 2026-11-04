---
type: llm
focus: trace
weight: 1
---

PASS if, up to the end of the run (which ends at the reconfigure question), nothing is changed: CLAUDE.md and AGENTS.md are not written or edited, and .claude/bruhs.json is not deleted, moved or edited.

FAIL if any of those files is changed before the user answers.
