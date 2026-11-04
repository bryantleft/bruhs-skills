---
type: llm
focus: trace
weight: 1
---

PASS if, as the user asked for a new project, the run calls mcp__linear-bnle__linear_create_project for my-app with teamIds containing the BNLE team id, rather than reusing the existing Core project.

FAIL if no project is created, it is created on another server or team, or the run files everything under Core.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
