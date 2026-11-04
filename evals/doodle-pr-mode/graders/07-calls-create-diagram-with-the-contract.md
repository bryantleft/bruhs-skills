---
type: llm
focus: trace
weight: 1
---

PASS if the run calls mcp__tldraw__create_diagram once (or retries after an error) with a `shapes` array, `format: "png"`, `width: 1920` and `height: 1080`, and uses the returned path (.tldraw/diagram.png) in the next step.

FAIL if it never calls create_diagram, sends other dimensions or format without a reason, or ignores the returned path.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
