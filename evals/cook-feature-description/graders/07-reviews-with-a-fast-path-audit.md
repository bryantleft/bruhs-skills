---
type: llm
focus: trace
weight: 1
---

PASS if Step 6 dispatches a reviewer subagent (or reviews inline on a harness without subagents) whose brief includes the fast-path audit: N+1 queries, await in loops, per-request clients, and the decision audit for numbers without receipts.

FAIL if no review step runs, or the review brief leaves out the fast-path audit.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
