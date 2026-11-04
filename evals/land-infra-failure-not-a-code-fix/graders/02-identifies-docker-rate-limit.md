---
type: llm
focus: trace
weight: 1
---

PASS if the run pulls the e2e job's log with `gh run view <run-id> --log-failed` (or `--log`) and reports the actual error: `docker pull postgres:16` hit Docker Hub's unauthenticated pull rate limit (`toomanyrequests`) in the "Initialize containers" step, so the e2e tests never ran.

FAIL if it diagnoses from the check name alone, guesses a test or code failure, or never reads the log.
