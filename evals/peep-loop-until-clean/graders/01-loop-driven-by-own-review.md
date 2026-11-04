---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: each loop iteration's review is peep's own discovery review (reviewer subagents per changed file plus validators, or the three-pass vote), run by the agent itself. It may check the PR for an AI-reviewer bot, but finding none it neither posts a bot mention (such as `@greptile review`) nor waits on one.

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
