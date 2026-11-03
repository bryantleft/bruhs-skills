---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: For the must-fix thread, the subagent runs the reproduction loop: writes a minimal failing test beside lib/db/queries.ts, runs it against current code and captures RED_OUTPUT (must fail), applies the fix, re-runs and captures GREEN_OUTPUT (must pass), then reverts the fix AND deletes the repro test and confirms `git diff --stat` is empty

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
