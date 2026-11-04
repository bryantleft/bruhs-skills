---
type: llm
focus: trace
weight: 1
---

PASS if the report asks for the evidence needed to set the timeout, retry and concurrency policy: for example upstream latency percentiles, the Identity team's rate limits or quotas, error-rate data, or capacity math for the connection pool, noting the upstream doc does not provide them.

FAIL if it asks for no evidence, or treats a generic best practice as enough.
