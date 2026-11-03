---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats 'PERDIX-145' as a literal feature description instead of a ticket ID and never calls linear_get_issue
- Loads the wrong MCP tool (e.g. mcp__linear__linear_get_issue instead of the mcpServer-scoped mcp__linear-perdix__linear_get_issue)
- Drops the ticketContext so yeet later creates a duplicate Linear ticket

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
