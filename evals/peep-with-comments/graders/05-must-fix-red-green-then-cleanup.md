---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: for the must-fix thread on lib/db/queries.ts:45, a test asserting that getTopAgents returns the highest winRate first is run against the current code and FAILS (RED), passes after the sort-by-winRate-descending fix (GREEN), and afterwards the trial fix is reverted and the repro test file deleted, with the subagent reporting a clean `git diff --stat` / `git status`.

FAIL if it does not, or if the run never reached the step this describes.

The evidence may appear in the subagent's returned report rather than as top-level tool calls.
