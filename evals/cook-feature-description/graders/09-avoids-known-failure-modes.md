---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Tries to fetch a Linear ticket for a plain-English feature description
- Skips the AskUserQuestion approach-selection step and picks an approach unilaterally
- Invents multiple cosmetic variants just to hit an approach count
- Introduces a concurrency, cache, timeout, or pagination number without a receipt
- Invokes a non-existent Skill('agent-browser') for visual verification instead of /expect
- Marks the UI feature done by eyeballing it, without /expect verification or any screenshot/recording capture
- Ends with 'Using existing ticket' text even though cook was not started from a ticket ID

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
