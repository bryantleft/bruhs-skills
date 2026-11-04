---
type: llm
focus: trace
weight: 1
---

PASS if the run asks the user how to proceed, offering both 'Run /bruhs:claim' (marked as the recommended option) and 'Continue without config' (noting that Linear integration will be skipped). In a headless run the question arrives as a plain message with the options listed rather than through AskUserQuestion; either form counts.

FAIL if it doesn't ask, offers only one of the two options, or doesn't recommend claim.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
