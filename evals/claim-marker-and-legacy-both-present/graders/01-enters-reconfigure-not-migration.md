---
type: llm
focus: trace
weight: 1
---

PASS if the run finds the bruhs:state block in CLAUDE.md (Case A) and asks whether to reconfigure (Yes: re-detect and overwrite the block / No: keep it and exit), not the legacy-migration question. A plain-text question with those options counts the same as AskUserQuestion.

FAIL if it asks the "Migrate legacy config" question (Migrate / Re-detect from scratch / Cancel), asks both, or asks nothing and carries on.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
