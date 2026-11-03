---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Each subagent returns the STRICT format including EVIDENCE_TIER, REPRO_TEST, REPRO_COMMANDS, RED_OUTPUT, GREEN_OUTPUT — the must-fix at EVIDENCE_TIER: reproduced, the style nit (no bug claim) at fix-validated, the question at n/a

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
