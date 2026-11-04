---
type: llm
focus: trace
weight: 1
---

PASS if the run asks the user whether to reconfigure, offering at least these two choices: Yes (re-detect and overwrite the block) and No (keep the existing configuration and exit), and then stops to wait for the answer. A plain-text question with those options counts the same as AskUserQuestion.

FAIL if it does not ask, asks something else (such as a migrate question), or picks an answer for the user and carries on.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
