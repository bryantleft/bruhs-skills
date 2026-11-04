---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Copies common defaults such as three retries, an exponential delay, or a five-minute TTL without evidence
- Treats environment variables as receipts even though their values have no rationale
- Falls back to stale cache data while returning an indistinguishable success result
- Adds comments describing assumptions without executable validation or monitoring
