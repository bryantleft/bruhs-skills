---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Runs an iterative loop (default max 5) driven by peep's OWN discovery review (Step 3: subagent-per-file + validator, or 3-pass vote) — it does NOT require or wait on an external AI-reviewer bot

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
