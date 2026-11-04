---
type: llm
focus: trace
weight: 1
---

PASS if the run ends by asking the user which command they meant, either as the interactive command menu or as a clarifying question, and waits for the answer. A plain-text question counts the same as AskUserQuestion.

FAIL if it ends without a question, or picks a command for the user and runs it.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
