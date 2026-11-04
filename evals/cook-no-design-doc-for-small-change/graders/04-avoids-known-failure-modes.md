---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Writes a design doc for a one-component reversible change, even a short one in docs/design/
- Asks the user whether to write a design doc when no trigger applies
- Runs the design-doc review gates (cold-read subagent, approval request) for this change

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
