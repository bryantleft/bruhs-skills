---
type: llm
focus: trace
weight: 1
---

PASS if, after the report, the run asks the user whether to fix the issues interactively or keep the report only (via AskUserQuestion or by asking in its reply), and stops there.

FAIL if it does not ask, or goes on to fix issues without an answer.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
