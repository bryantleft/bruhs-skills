---
type: llm
focus: trace
weight: 1
---

PASS if the run makes no Linear MCP calls (no mcp__linear-sonner__* or other linear_* tool) before the user answers the reconfigure question.

FAIL if any Linear tool is called during the run.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
