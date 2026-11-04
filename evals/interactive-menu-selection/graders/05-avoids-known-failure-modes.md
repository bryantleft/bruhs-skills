---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Silently picks a default command instead of asking
- Offers slop in the menu although SKILL.md excludes it
- Invents a feature description or ticket and starts cook with it
- Tells the user to type a command name without showing what the commands are

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
