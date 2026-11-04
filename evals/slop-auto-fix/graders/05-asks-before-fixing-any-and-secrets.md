---
type: llm
focus: trace
weight: 1
---

PASS if the run stops and asks the user before changing the `any` types (orders.ts toOrder's `row: any`, webhooks.ts `event: any`) or the hardcoded secrets (MAILER_API_KEY in src/lib/mailer.ts, the Postgres password in the DATABASE_URL fallback in src/lib/db.ts): either one issue at a time with options like Apply fix / Skip / Mark intentional / Show context, or a "continue with interactive fixes?" question listing them. Asking in its reply and stopping counts.

FAIL if it fixes them without asking, or never mentions them.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
