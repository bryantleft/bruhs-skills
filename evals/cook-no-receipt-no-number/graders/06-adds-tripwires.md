---
type: llm
focus: trace
weight: 1
---

PASS if the design adds executable tripwires for exhausted retry policy, stale data, and invalid configuration (for example startup validation in src/config.ts that rejects missing or nonsensical retry/cache settings, a metric or alert when retries are exhausted or stale data is served, and tests for each).

FAIL if these assumptions are covered only by comments, TODOs or logs followed by success.
