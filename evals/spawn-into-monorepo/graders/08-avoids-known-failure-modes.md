---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Scaffolds the Hono app at the repo root instead of apps/api
- Overwrites the bruhs:state block with only the new app's config instead of merging
- Writes stack.framework (a string) instead of stack.frameworks (an array) in this monorepo
- Says the app is set up and running when the scaffold failed
- Calls Linear tools on a server other than linear-perdix

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
