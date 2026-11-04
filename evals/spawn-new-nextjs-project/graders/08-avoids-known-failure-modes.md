---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Uses npm, npx, yarn or bun to create the project although the command doc says to always use pnpm for TypeScript projects
- Says the project is set up and ready when the scaffold failed
- Calls Linear tools on a server other than linear-bnle (e.g. mcp__linear__linear_create_issue)
- Ends the run asking about stack choices the user already made

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
