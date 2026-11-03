---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Posts a bare-prose reply to the question thread instead of a Conventional Comments-formatted one
- Spawns subagents sequentially (one at a time, awaiting each) instead of in a single parallel tool-call message
- Analyzes all 4 comments in a single shared context, allowing findings from one thread to bias another
- Reports the must-fix as confirmed on the strength of 'tsc + tests pass' without ever writing a test that FAILS on current code — i.e. proves the fix builds but not that the bug was real
- Leaves the repro test file behind after validation instead of deleting it, leaving the working tree dirty
- Skips the full-suite validation in Step 10 because per-fix validation already passed, missing cross-file type conflicts

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
