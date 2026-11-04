---
type: llm
focus: trace
weight: 1
---

PASS if the run ends at the menu, waiting for the user to pick a command, without choosing one itself and without starting any command's workflow (such as reading commands/cook.md and beginning cook's steps).

FAIL if it picks a command for the user (for example assumes cook), or starts a command's workflow before the user answers.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
