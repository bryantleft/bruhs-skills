---
type: llm
focus: trace
weight: 1
---

PASS if Phase 2 ends by asking "Which would you like to grill?" (or the same question in close wording, via AskUserQuestion or in its reply) and the run stops there.

FAIL if it does not ask, or picks a candidate itself and starts grilling it.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
