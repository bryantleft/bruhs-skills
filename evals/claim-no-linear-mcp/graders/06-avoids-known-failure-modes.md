---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Attempts a ToolSearch or call for mcp__linear__linear_get_teams (or any linear tool) although no Linear server is configured
- Writes integrations.linear with null or empty strings instead of omitting it
- Copies the doc's example tooling.mcps (["linear", "notion", "context7"]) instead of what was detected
- Aborts the claim because Linear is missing, although Linear is optional

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
