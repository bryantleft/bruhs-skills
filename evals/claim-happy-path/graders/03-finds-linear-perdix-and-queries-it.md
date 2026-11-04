---
type: llm
focus: trace
weight: 1
---

PASS if the run discovers the linear-perdix server from the user's MCP config (for example by running detect_mcp_servers.py, or by reading ~/.claude.json), and then calls mcp__linear-perdix__linear_get_teams and mcp__linear-perdix__linear_list_projects to get the real team and project.

FAIL if it never finds linear-perdix, calls Linear tools on another server name (such as mcp__linear__...), or picks a team or project without querying Linear.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
