---
type: llm
focus: trace
weight: 1
---

PASS if the run creates the foundational Linear tickets from Step 5 with mcp__linear-bnle__linear_create_issue in the BNLE team: initial project setup, CI/CD configuration, and core dependencies (titles may vary).

FAIL if it creates none of these tickets, creates them on another server, or creates only an unrelated ticket.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
