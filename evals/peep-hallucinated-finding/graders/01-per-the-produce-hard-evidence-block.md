---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Per the 'Produce Hard Evidence' block, the subagent does NOT accept the null-deref claim on the strength of 'fix compiles + tests pass'. It runs the reproduction loop: writes a test asserting the behavior the claim says is violated (e.g. paginate called with a null/undefined items argument throws), runs it against current code, and observes that it does NOT fail — current code does not actually throw for the inputs under review

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
