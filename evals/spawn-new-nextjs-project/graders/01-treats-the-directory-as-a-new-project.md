---
type: llm
focus: trace
weight: 1
---

PASS if the run checks for monorepo markers (turbo.json, pnpm-workspace.yaml), finds none, and goes straight to creating a new project, without asking the "What would you like to add to this monorepo?" (Add to repo) question.

FAIL if it asks the Add to repo question, or treats the directory as a monorepo.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
