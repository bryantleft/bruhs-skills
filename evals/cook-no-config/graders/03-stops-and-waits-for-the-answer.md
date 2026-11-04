---
type: llm
focus: trace
weight: 1
---

PASS if, after asking, the run stops and waits for the user's answer: it does not start the claim workflow, write a bruhs:state block into CLAUDE.md or AGENTS.md, create .claude/bruhs.json, or go on to explore, plan or build the profile page.

FAIL if it picks an option itself and carries on, or does any of the above before the user answers.
