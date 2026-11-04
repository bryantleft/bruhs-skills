---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: in the first iteration it fixes the off-by-one in src/lib/retry.ts (the loop starting at 1, so `attempts: 3` calls fn only twice) on the strength of a test that fails on current code (RED) and passes after the fix (GREEN).

FAIL if it does not, or if the run never reached the step this describes.

The evidence may appear in a subagent's returned report rather than as top-level tool calls.
