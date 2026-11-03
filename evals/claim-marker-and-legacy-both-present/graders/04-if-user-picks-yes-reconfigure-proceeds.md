---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If user picks 'Yes' (reconfigure): proceeds through Step 2–7, writes a fresh bruhs:state block. After writing, fires the delete-prompt AskUserQuestion for the legacy file (same prompt as the Migrate path)

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
