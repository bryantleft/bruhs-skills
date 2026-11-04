---
type: llm
focus: trace
weight: 1
---

PASS if the run ends by asking the user to approve the design doc (pointing at its path) before any implementation, and stops there: no source files under src/ are created or changed.

FAIL if it implements anything before approval, treats the user's "go with your recommendation" as approval of the doc, or ends without asking.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
