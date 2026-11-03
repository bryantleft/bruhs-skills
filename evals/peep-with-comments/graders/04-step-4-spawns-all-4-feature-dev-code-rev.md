---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 4 spawns ALL 4 feature-dev:code-reviewer subagents in a single tool-call message (parallel, no context bleed) — each with the per-thread prompt including PR title/description, comment, file path/line, categorization instructions, and the 'Produce Hard Evidence' reproduction-first block

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
