---
type: llm
focus: trace
weight: 1
---

PASS if, right after persisting and before exploration continues, the run tells the user which skill it added to bruhs:state (along the lines of "✓ Added stripe-best-practices to bruhs:state (CLAUDE.md + AGENTS.md)").

FAIL if the write happens without telling the user, or the message only comes much later or names the wrong skill.
