---
type: llm
focus: trace
weight: 1
---

PASS if the report flags TIMEOUT_MS = 5000, MAX_RETRIES = 3 and CONCURRENCY = 20 in src/profile-client.ts as operational numbers with no receipt, and does not propose replacement values for them (no "use 2000 ms", "retry twice", "limit to 10").

FAIL if any of the three is not flagged, or the report suggests specific new numbers as the fix.
