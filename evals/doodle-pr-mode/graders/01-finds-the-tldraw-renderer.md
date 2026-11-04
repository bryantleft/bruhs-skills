---
type: llm
focus: trace
weight: 1
---

PASS if the run checks for the tldraw render tool (for example ToolSearch for mcp__tldraw__create_diagram), finds it, and carries on with the pr pipeline rather than aborting or printing an install hint.

FAIL if it concludes the renderer is missing, or aborts.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
