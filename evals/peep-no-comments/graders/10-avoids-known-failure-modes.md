---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Silently exits with 'no comments, nothing to do' instead of reviewing
- Runs the per-file reviews one after another instead of launching them together
- Skips the validator pass and surfaces reviewer findings directly
- Reports a bug claim as confirmed on 'the fix compiles + tests pass' without a test that fails on current code
- Surfaces naming/formatting/magic-number suggestions as findings
- Fails to write the shown findings to .claude/.peep-history/PR-73.jsonl
- Leaves a fix applied to source files, commits, pushes, or posts anything to the PR although the user asked for a report only (temporary repro edits that are reverted, the history file and the .gitignore entry are expected)

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
