---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it launches one isolated subagent per unresolved thread (4 in total), all started together in a single batch rather than one after another, and each subagent's brief carries the PR title/description, that thread's comment, its file path and line, categorization instructions, and the reproduction-first evidence instructions.

FAIL if it does not, if it analyzes the threads in one shared context, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
