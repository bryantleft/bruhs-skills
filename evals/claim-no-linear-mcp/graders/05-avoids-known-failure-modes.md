---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Attempts ToolSearch for mcp__linear__linear_get_teams even though no Linear server is configured
- Writes integrations.linear with null/empty strings instead of omitting the whole section
- Aborts the claim entirely because Linear is missing, even though Linear is optional per the command doc

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
