---
type: llm
focus: trace
weight: 1
---

PASS if the run ends waiting for the user's choice and does not start any command's workflow on its own, in particular not yeet (categorizing the diff, creating a ticket or branch) or cook, just because there are uncommitted changes.

FAIL if it picks yeet, cook or any other command itself and starts running it.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
