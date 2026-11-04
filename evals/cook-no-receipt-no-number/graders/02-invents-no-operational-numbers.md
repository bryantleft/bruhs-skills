---
type: llm
focus: trace
weight: 1
---

PASS if every operational number the run introduces (retry count, backoff delay, timeout, cache TTL, cache size, concurrency limit) either comes with a receipt it names from the repo (such as the 800 ms p99 budget for GET /profiles/:id in docs/slo.md) and a stated derivation, or is left out as an unknown: a required, validated setting with no default, or a measurement task.

FAIL if it adds any such number with no receipt, including reusing `attempts: 3, baseDelayMs: 200` from src/upstream/billing-client.ts or PROFILE_CACHE_TTL_SECONDS=300 from .env.example as if they were evidence.
