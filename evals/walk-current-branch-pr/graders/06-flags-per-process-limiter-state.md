---
type: llm
focus: trace
weight: 1
---

PASS if the Risk callouts say that the limiter's counters live in an in-memory Map inside each process, so with the 3 replicas in deploy/app.yaml a client can get up to about 3x the documented 100 req/min quota (or, equivalently, that the limit is not shared across instances). Also counting it if the same callout notes the Map never evicts old client keys.

FAIL if no risk callout addresses the limiter's state not being shared across the replicas.
