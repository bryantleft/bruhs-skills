---
type: llm
focus: trace
weight: 1
---

PASS if the run finds linear-sonner from the user's MCP config (e.g. detect_mcp_servers.py or ~/.claude.json), calls mcp__linear-sonner__linear_get_teams and mcp__linear-sonner__linear_list_projects, and uses the team (Son, key SON) and project (Core) the user named, with the ids those calls returned, without asking again.

FAIL if it skips the Linear calls and copies ids from the legacy file without checking, uses another server, or ends the run asking which team or project to use.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
