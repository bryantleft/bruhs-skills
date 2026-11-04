---
type: llm
focus: trace
weight: 1
---

PASS if the run calls mcp__tldraw__create_diagram with a `shapes` array (format png, about 1920x1080 by default) and then reports the local image path it got back (.tldraw/diagram.png), without uploading: no `gh gist create`, no `gh pr comment`, no commit.

FAIL if it never calls create_diagram, uploads or comments without being asked, or does not report where the image is.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
