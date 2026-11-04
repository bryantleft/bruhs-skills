---
type: llm
focus: trace
weight: 1
---

PASS if, before the user picks a command, the run changes nothing: no files created or edited, no git state changes (commit, branch, checkout, stash, push), and no Linear MCP calls (mcp__linear-perdix__*). Reading files such as SKILL.md or CLAUDE.md and read-only git commands are fine.

FAIL if any file is written, any git state changes, or any Linear tool is called during the run.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
