---
type: llm
focus: trace
weight: 1
---

PASS if the run presents the bruhs command menu that SKILL.md defines for a bare /bruhs: the options spawn, claim, cook, yeet, peep, doodle, dip, deepen and drill, each with a short description. All nine must be offered; order and grouping don't matter (splitting them over several questions because of a 4-option limit is fine), and offering other non-slop commands as well (verify, walk, land, recap) is fine. A plain-text numbered list counts the same as AskUserQuestion.

FAIL if it offers only some of those nine, offers no menu, or asks an open question ("what do you want to do?") with no list of commands.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
