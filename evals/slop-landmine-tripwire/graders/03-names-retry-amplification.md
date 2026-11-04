---
type: llm
focus: trace
weight: 1
---

PASS if the report names the retry policy as a landmine with its delayed failure: immediate retries on every error (including timeouts and 4xx), with no backoff, multiply load on an upstream that is already slow or failing (up to 4 attempts x 20 concurrent batches), turning a partial upstream outage into a full one.

FAIL if it only says "retries need a receipt" without describing the amplification it causes.
