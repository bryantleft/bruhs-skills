---
type: llm
focus: trace
weight: 1
---

PASS if the run says which receipts are missing (profile-service's latency, error rate, rate limit and retry policy, all TBD in docs/slo.md, and how stale a profile may be for the mobile app) and proposes a concrete way to get each: a measurement of the upstream path, or a contract to ask the identity team or the profile consumers for.

FAIL if it notes that numbers are unknown without saying what evidence would settle each, or treats an existing env var or example as that evidence.
