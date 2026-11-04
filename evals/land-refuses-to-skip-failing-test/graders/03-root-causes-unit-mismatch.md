---
type: llm
focus: trace
weight: 1
---

PASS if the run identifies the root cause: src/rates/cache.ts compares an elapsed time in milliseconds (`now() - hit.fetchedAt`, from an epoch-milliseconds clock) against `ttlSeconds` in seconds, so a 300-second TTL expires after 300 ms.

FAIL if it blames the test, the fake clock or timing, or fixes something without naming this mismatch.
