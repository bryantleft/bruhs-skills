---
type: llm
focus: trace
weight: 1
---

PASS if the run looks for feature-specific skills because the work involves Stripe, by any available means (Skill('find-skills') if present, the harness's skill list, or searching the repo), finds .claude/skills/stripe-best-practices/SKILL.md, notes that it is not in tooling.skills, and loads or reads it for this feature.

FAIL if it never looks for a Stripe skill, or finds it and doesn't use it.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
