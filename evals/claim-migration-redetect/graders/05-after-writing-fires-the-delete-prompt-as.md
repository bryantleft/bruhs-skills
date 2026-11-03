---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: After writing, fires the delete-prompt AskUserQuestion (legacy file still exists, ignored from now on). User picks 'Yes, delete' → .claude/bruhs.json is removed. User picks 'No, keep both' → legacy file is left alone (it will be ignored by read_bruhs_block.py since the marker block now exists)

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
