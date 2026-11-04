---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 2 maps the settings page, the preferences module and where theme state would live, through an explorer subagent (references/harness-tools.md: feature-dev:code-explorer, Explore or general-purpose in Claude Code) or by exploring inline when no subagent is available; and it loads the skills listed in config.tooling.skills, or says none are listed

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
