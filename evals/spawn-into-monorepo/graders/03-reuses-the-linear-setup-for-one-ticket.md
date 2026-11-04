---
type: llm
focus: trace
weight: 1
---

PASS if the run reuses the Linear config already in bruhs:state (linear-perdix, team 9ffd07ac-0000-4000-8000-000000000000, project Core) and creates a ticket for setting up the api app with mcp__linear-perdix__linear_create_issue in that team, without asking the user to pick a workspace, team or project again. Creating extra setup tickets is fine; creating a new Linear project is not needed.

FAIL if no ticket is created for the api app, it is created on another server or team, or the run ends asking which Linear team or project to use.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
