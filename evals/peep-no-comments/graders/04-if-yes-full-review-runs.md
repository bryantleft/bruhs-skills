---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If 'Yes - full review': runs `gh pr diff 73 --name-only` then spawns one feature-dev:code-reviewer subagent per changed file, ALL in parallel in one tool-call message, each using the file-scoped review prompt with the priority order (bugs > security > perf anti-patterns > edge cases > API contract) and the 'Produce Hard Evidence' reproduction-first block that sets EVIDENCE_TIER (reproduced / tooling-confirmed / fix-validated / unverified). Each bug claim is demonstrated with a RED→GREEN repro before being reported, and any claim whose repro passes on current code is dropped

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
