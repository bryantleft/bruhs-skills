---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Because the repro PASSES on current code (RED never reached), the subagent DROPS the null-deref finding entirely — it was a hallucination — rather than reporting it (the anti-hallucination gate in step 4 of the reproduction loop / discovery loop)

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
