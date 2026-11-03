---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If the subagent additionally inspects the real off-by-one and wants to flag it, it must reproduce it first: a test asserting page 1 returns the first page FAILS on current code (RED, e.g. actual [3,4] vs expected [1,2]) and PASSES after `(page-1)*pageSize` (GREEN) — only then is it surfaced as EVIDENCE_TIER: reproduced

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
