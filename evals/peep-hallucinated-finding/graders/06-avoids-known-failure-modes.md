---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Surfaces a null-deref (or any other) must-fix as confirmed because applying a guard left typecheck and the existing tests green
- Reports the off-by-one, or any bug, as confirmed from inspection alone without a test that fails on current code
- Labels a bug finding reproduced without ever capturing a failure on current code
- Applies a fix, commits, pushes or posts to the PR although the user asked for a report only
- Leaves repro tests or trial edits behind in the working tree

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
