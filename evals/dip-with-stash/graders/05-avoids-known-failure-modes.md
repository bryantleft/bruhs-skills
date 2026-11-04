---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Pops, applies or drops a stash without the user's answer
- Treats the user's "try serif headings" stash as a bruhs stash, or touches it
- Misses the bruhs stash because of a wrong grep pattern
- Uses `git checkout main` instead of `git switch main`, or force-deletes with `git branch -D`

Warnings that git could not update .git/config (for example after deleting a branch) are an environment quirk, not a failure.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
