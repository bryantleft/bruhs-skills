---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Silently picks a default subcommand instead of asking via AskUserQuestion
- Includes slop in the interactive menu despite SKILL.md stating it is intentionally excluded
- Jumps directly into cook's Step 1 exploration without receiving a feature description or ticket ID

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
