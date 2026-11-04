---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it lists the changed files (`gh pr diff 73 --name-only` or equivalent) and launches one reviewer subagent per changed file, all started together in one batch, each brief carrying the priority order (bugs, security, performance anti-patterns, edge cases, API contract) and the reproduction-first evidence instructions with EVIDENCE_TIER.

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
