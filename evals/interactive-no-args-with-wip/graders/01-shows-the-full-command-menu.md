---
type: llm
focus: trace
weight: 1
---

PASS if the run presents the bruhs command menu that SKILL.md defines for a bare /bruhs (the 13 commands spawn, claim, cook, verify, yeet, walk, land, peep, dip, recap, doodle, deepen and drill, without slop; any order, and a first question offering the four groups counts when each group's description names its commands), even though the working tree is dirty. Noting the uncommitted changes, or suggesting that yeet fits them, is fine as long as the full menu is offered and the user chooses. A plain-text numbered list counts the same as AskUserQuestion.

FAIL if it offers no menu, offers only a WIP-related subset (e.g. just yeet or "commit these changes?"), or omits any of the 13 commands.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
