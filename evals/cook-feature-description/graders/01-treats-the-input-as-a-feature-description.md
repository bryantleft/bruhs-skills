---
type: llm
focus: trace
weight: 1
---

PASS if Step 1 treats 'add a leaderboard to the game page' as a feature description (not a ticket ID), prints a short Feature / Goal / Scope summary, and never calls mcp__linear-perdix__linear_get_issue or any other Linear tool to look it up.

FAIL if it calls a Linear tool for this input, or skips the summary.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
