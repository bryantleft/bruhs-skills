---
type: llm
focus: trace
weight: 1
---

PASS if the run reads PR #64's checks with `gh pr checks`, pulls the failing `test` job's log with `gh run view <run-id> --log-failed`, and names the failure from it: "serves a cached rate within the TTL" in src/rates/cache.test.ts expected 1 fetch and got 2.

FAIL if it never reads the CI log, or names a different failure.
