---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: for the must-fix thread on lib/db/queries.ts:45, a repro test asserting that getTopAgents returns the highest winRate first is run against the current, unmodified code and FAILS (RED), and that failure output is captured.

FAIL if it does not, or if the run never reached the step this describes.

The evidence may appear in a subagent's returned report rather than as top-level tool calls.
