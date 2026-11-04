---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: after the file reviewers return, it launches one validator subagent per proposed issue, together in one batch, each told to try to falsify the claim by re-running the reproduction itself; the run then drops rejected findings and keeps or demotes the rest according to the validator verdicts.

FAIL if it does not, if it surfaces reviewer findings without a validator pass, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
