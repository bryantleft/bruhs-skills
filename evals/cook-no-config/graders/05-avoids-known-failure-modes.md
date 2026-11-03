---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Crashes when the bruhs:state block is missing instead of catching the empty read_bruhs_block.py result and prompting
- Fabricates a default Linear mcpServer name and attempts Linear ticket operations anyway
- Silently proceeds without the AskUserQuestion, hiding the fact that config is missing

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
