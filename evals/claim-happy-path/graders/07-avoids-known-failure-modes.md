---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Hardcodes structure as 'monorepo' despite no turbo.json / pnpm-workspace.yaml being present
- Skips the Linear team/project AskUserQuestion and writes null IDs into the bruhs:state block
- Omits vercel-react-best-practices from tooling.skills even though Next.js was detected

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
