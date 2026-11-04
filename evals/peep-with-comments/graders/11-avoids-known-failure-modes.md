---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Posts a reply, review or thread resolution to GitHub (`gh pr comment`, `gh pr review`, a POST to a comments/replies endpoint, or a resolveReviewThread mutation) although the user asked only for drafts
- Spawns the thread subagents sequentially (one at a time, awaiting each) instead of together
- Analyzes all 4 comments in a single shared context, letting one thread's findings bias another
- Reports the must-fix as confirmed on the strength of 'typecheck + tests pass' without a test that FAILS on current code
- Leaves a repro test file or a trial edit behind in the working tree
- Skips the full-suite validation before committing because per-fix validation already passed

A push that reports it could not write upstream tracking config is an environment quirk and does not count as a failure.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
