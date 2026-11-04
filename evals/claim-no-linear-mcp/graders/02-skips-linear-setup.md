---
type: llm
focus: trace
weight: 1
---

PASS if the run skips the Linear workspace / team / project step entirely: no mcp__linear* tool is loaded or called, and no workspace, team or project question is asked.

FAIL if it tries to load or call any Linear tool (e.g. a ToolSearch for mcp__linear__linear_get_teams), or asks the user to pick a Linear team or project.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
