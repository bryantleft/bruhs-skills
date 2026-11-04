---
type: llm
focus: trace
weight: 1
---

PASS if the run detects the existing node:test suite (the `test` script in package.json and src/lib/agent-record.test.ts), writes a failing test for the leaderboard's logic before the implementation, makes it pass, and keeps the new test in the suite rather than deleting it.

FAIL if it writes implementation before any test, never runs the test it wrote, or deletes tests from a project that has a suite.
