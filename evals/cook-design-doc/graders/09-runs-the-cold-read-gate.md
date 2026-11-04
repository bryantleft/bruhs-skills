---
type: llm
focus: trace
weight: 1
---

PASS if, after drafting the doc, the run has a fresh subagent read only the doc and state the problem, the proposal, the riskiest part and the likely pushback (the cold-read gate in practices/design-docs.md), then fixes in the doc whatever that read got wrong or missed (or says the read found nothing to fix).

FAIL if no cold read runs, the cold reader is given extra context beyond the doc, or its findings are ignored. FAIL if no doc is written.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
