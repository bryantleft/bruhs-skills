---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Writes structure "monorepo" although there is no turbo.json, pnpm-workspace.yaml, nx.json or lerna.json
- Writes integrations.linear with a null or placeholder team or project id
- Omits vercel-react-best-practices from tooling.skills although Next.js was detected
- Writes the old .claude/bruhs.json instead of the CLAUDE.md / AGENTS.md blocks
- Says the config was written when the sync script failed or was never run

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
