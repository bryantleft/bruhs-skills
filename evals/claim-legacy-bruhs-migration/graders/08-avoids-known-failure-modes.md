---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Re-runs stack detection or Linear selection on the migrate path and overwrites the legacy team/project ids
- Deletes .claude/bruhs.json without asking first
- Writes only CLAUDE.md and not AGENTS.md
- Truncates or rewrites hand-written CLAUDE.md content outside the blocks
- Writes the state block but not the rules block
- Reports a successful migration when a sync script call failed

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
