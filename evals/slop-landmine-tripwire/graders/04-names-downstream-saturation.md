---
type: llm
focus: trace
weight: 1
---

PASS if the report names the fan-out as a landmine with its delayed failure: getProfiles() over a large id list runs waves of 20 concurrent upstream requests with no bound tied to the upstream's capacity or quota, so one large feed render can saturate the upstream or the connection pool.

FAIL if concurrency is mentioned only as a missing receipt, with no delayed failure described.
