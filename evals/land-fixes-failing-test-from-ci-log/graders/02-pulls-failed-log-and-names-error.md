---
type: llm
focus: trace
weight: 1
---

PASS if the run pulls the failing `test` job's log with `gh run view <run-id> --log-failed` (the run id taken from the check's link, 71000000xx) and states the first actionable error from it: the test "rounds a partial period to the nearest cent" in src/billing/proration.test.ts expected 1667 and got 1666.

FAIL if it diagnoses from the check name alone, from local test output only without ever reading the CI log, or names a different cause.
