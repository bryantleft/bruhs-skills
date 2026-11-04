---
type: llm
focus: trace
weight: 1
---

PASS if, before `gh pr create`, the run gives only the PR body to a fresh subagent (or, on a harness without subagents, does the read-back itself as if it had no other context) and asks what changes, what is riskiest, what deviates, and which terms it couldn't define, then fixes the body where the answers were wrong or unclear.

FAIL if it never runs a read-back on the body before creating the PR.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
