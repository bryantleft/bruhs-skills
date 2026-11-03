---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Re-runs stack detection (Steps 2–6) on the migrate path, potentially overwriting the user's selected Linear team/project with auto-detected defaults
- Auto-deletes .claude/bruhs.json without the second AskUserQuestion
- Skips writing AGENTS.md (writes only CLAUDE.md) — breaks the mirror invariant
- Truncates or rewrites hand-written CLAUDE.md content outside the block
- Skips the rules block (writes state only) — leaves the user without stack-derived rules
- Falls through to Case C (fresh setup) despite the legacy file being present

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
