---
type: llm
focus: trace
weight: 1
---

PASS if the run presents the bruhs command menu that SKILL.md defines for a bare /bruhs: all 13 commands, spawn, claim, cook, verify, yeet, walk, land, peep, dip, recap, doodle, deepen and drill, each with a short description. SKILL.md asks in two steps where a question holds at most 4 options: a first question offering the four groups (Start or build, Ship a PR, After merge, Investigate), whose descriptions name every command, counts as offering all 13. So does one grouped, numbered list of the 13. Order doesn't matter. A plain-text numbered list counts the same as AskUserQuestion.

FAIL if it leaves any of those 13 out of what the user sees, offers no menu, or asks an open question ("what do you want to do?") with no list of commands.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
