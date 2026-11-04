---
type: llm
focus: trace
weight: 1
---

PASS if the run checks for Linear servers (detect_mcp_servers.py or the agent's MCP config), finds none, and, as the user said to skip Linear, carries on without it: no mcp__linear* tool is loaded or called and no Linear project or tickets are created or claimed.

FAIL if it tries to load or call a Linear tool, claims tickets were created, or stops to ask about Linear although the user said to skip it.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
