---
type: llm
focus: trace
weight: 1
---

PASS if the run checks whether a tldraw render tool is available under either name doodle supports, mcp__tldraw__create_diagram and mcp__tldraw-render__create_diagram (for example ToolSearch for each, or by inspecting the tools it has), and concludes neither is installed.

FAIL if it never checks, checks only one name and proceeds as if it existed, or concludes a renderer is available.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
