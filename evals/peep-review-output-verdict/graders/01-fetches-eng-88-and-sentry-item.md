---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: before reviewing, it fetches ticket ENG-88 from Linear and the linked Sentry issue BILLING-4F2, and uses ENG-88's acceptance criteria (tax rounded once on the subtotal) as the intent the review checks against.

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
