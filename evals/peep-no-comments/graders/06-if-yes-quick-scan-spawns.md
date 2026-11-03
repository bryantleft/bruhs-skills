---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If 'Yes - quick scan': spawns THREE reviewer subagents in parallel over `gh pr diff 73` output with shuffled file orderings (seeds 1, 2, 3), then merges by consensus — keeps only issues that appear in >=2 of 3 passes (fuzzy-matched by file + line ±3 + summary token overlap), bumps confidence on 3-of-3 agreement, records VOTE_COUNT: n/3, THEN runs the reproduction pass on each surviving bug to assign EVIDENCE_TIER (consensus across opinions is not evidence — a survivor whose repro passes on current code is dropped)

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
