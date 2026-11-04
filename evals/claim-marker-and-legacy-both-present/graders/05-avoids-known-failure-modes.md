---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Fires the legacy migration prompt although the marker block is present
- Deletes .claude/bruhs.json without asking the user
- Merges the legacy file's values into the state block
- Says there is no legacy file
- Calls Linear tools (mcp__linear-perdix__* or mcp__linear-sonner__*) before the user answers

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
