---
type: llm
focus: trace
weight: 1
---

PASS if Step 2, before exploring, tries to load each configured skill (superpowers, shadcn, vercel-react-best-practices), and for each one that isn't available in this session says which skill is missing and carries on, as references/harness-tools.md says to.

FAIL if it skips loading the configured skills without a word, stops the workflow because one is missing, or claims to have loaded a skill that isn't available.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
