---
type: llm
focus: trace
weight: 1
---

PASS if the run finds the linear-bnle server from the user's MCP config (detect_mcp_servers.py, or reading ~/.claude.json), calls mcp__linear-bnle__linear_get_teams, and uses the Bnle team (key BNLE) the user named, with the team id that call returned.

FAIL if it never finds linear-bnle, calls Linear tools on another server name, or uses a team id that linear_get_teams did not return.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
