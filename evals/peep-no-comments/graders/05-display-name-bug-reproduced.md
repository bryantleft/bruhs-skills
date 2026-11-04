---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it reports the displayName() bug in src/lib/profile.ts (a user without a last name renders as "Ada undefined") backed by a test that fails on current code (RED) and passes after a fix (GREEN), with the trial fix and the repro test removed afterwards.

FAIL if it does not, or if the run never reached the step this describes.

The evidence may appear in a subagent's returned report rather than as top-level tool calls.
