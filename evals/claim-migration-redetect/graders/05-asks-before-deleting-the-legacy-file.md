---
type: llm
focus: trace
weight: 1
---

PASS if, after writing the new blocks, the run asks whether to delete the legacy .claude/bruhs.json (offering delete / keep), stops for the answer, and .claude/bruhs.json is still on disk at the end of the run.

FAIL if it deletes or moves the legacy file without asking, or never asks about it because this wasn't the migrate path.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
