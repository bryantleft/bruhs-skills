---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: After reviewers return, Step 3a spawns one validator subagent per proposed issue IN PARALLEL with adversarial 'try to falsify this claim' framing — the validator RE-RUNS the reproduction itself (not just re-reasons), reports EVIDENCE_REPLAYED, drops findings where the repro passes on current code (repro-passed-on-current-code), drops validator-rejected findings, and demotes validator-unsure findings to 'Unconfirmed — reasoning only'

FAIL if it does not, or if the run never reached the step this describes.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: asking the user directly for AskUserQuestion, loading or calling the tool directly for ToolSearch, the harness's own subagent or parallel-task facility for Task or a named subagent, and the same MCP server and tool under that harness's naming for an mcp__ tool.
