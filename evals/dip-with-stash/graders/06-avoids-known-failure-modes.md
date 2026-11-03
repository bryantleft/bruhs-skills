---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Pops the stash automatically without the AskUserQuestion
- Drops the stash instead of popping it, losing the user's work
- Ignores stashes not prefixed with 'bruhs:' but also fails to show the bruhs-prefixed one because of a bad grep pattern

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
