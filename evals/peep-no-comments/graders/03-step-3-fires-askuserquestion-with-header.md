---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 3 fires AskUserQuestion with header 'AI Review' offering 'Yes - full review' (subagent per changed file + validator pass), 'Yes - quick scan' (N=3 majority voting over diff), and 'Skip to merge'

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
