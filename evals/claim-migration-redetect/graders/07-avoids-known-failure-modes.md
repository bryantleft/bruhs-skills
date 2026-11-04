---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Writes framework "astro" or database "convex" into the new bruhs:state block
- Skips the "delete the legacy file?" question because this wasn't the migrate path
- Follows the Migrate path although the user asked to re-detect
- Refuses to re-detect because a config already exists
- Deletes .claude/bruhs.json without asking

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
