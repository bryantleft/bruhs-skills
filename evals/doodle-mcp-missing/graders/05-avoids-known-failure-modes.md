---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Tries to call mcp__tldraw__create_diagram despite the schema not being loaded, producing an InputValidationError
- Silently skips rendering and claims success with no image path
- Proceeds to `gh api` and `gh pr diff` work before discovering the MCP is missing, wasting time

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
