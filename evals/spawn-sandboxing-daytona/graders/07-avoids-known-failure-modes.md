---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Never offers or selects a Sandboxing / Daytona option although the project exists to run untrusted code
- Selects Daytona but omits the "sandboxing" key from the stack JSON, so derive_stack_rules.py can't pick it up
- Selects Daytona but the bruhs:rules block has no Daytona rules
- Invents a sandboxing provider that isn't an offered option (e.g. E2B, Firecracker)
- Calls Linear tools on a server other than linear-perdix

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
