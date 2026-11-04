---
type: llm
focus: trace
weight: 1
---

PASS if the run dispatches an explorer subagent (or, on a harness without subagents, explores inline and says so) that finds the game page src/app/game/[matchId]/page.tsx, the agentStats table in src/db/schema.ts, and the existing top-agents UI in src/app/stats/page.tsx with its query helpers in src/lib/stats.ts.

FAIL if it plans without locating these, or invents files that don't exist in the repo.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
