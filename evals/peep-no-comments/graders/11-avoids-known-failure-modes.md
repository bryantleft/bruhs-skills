---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Silently exits with 'no comments, nothing to do' instead of offering the AI review branch
- Runs 'full review' sequentially rather than dispatching all per-file subagents in parallel
- Skips the validator pass and surfaces unverified reviewer findings directly
- Reports bug claims as confirmed on 'the fix compiles + tests pass' without a RED test that fails on current code
- Surfaces a fictional finding as confirmed because the validator only re-reasoned instead of re-running the reproduction
- Runs only a single subagent on 'quick scan' instead of three with consensus merging
- Treats quick-scan consensus (>=2/3 agreement) as evidence and skips the reproduction pass on survivors
- Skips the lint-territory category filter and surfaces naming/formatting suggestions
- Re-surfaces findings the user already saw in a prior run (no cross-run dedupe)
- Fails to persist findings to .claude/.peep-history/PR-73.jsonl, breaking future dedupe
- Skips the priority hierarchy in the review prompt, reporting style and naming nits instead of real bugs

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
