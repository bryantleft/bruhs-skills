---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Because RED was reached but GREEN was not, the fix is NOT EVIDENCE_TIER: reproduced — the subagent reports the captured RED_OUTPUT and the failing post-fix output, sets EVIDENCE_TIER accordingly (unverified for the proposed fix, since it does not resolve the reproduction), and downgrades CONFIDENCE by 1

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
