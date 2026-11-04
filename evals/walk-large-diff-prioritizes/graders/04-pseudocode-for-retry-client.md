---
type: llm
focus: trace
weight: 1
---

PASS if src/lib/retryClient.ts gets a plain-English pseudocode summary of the retry loop (attempt, timeout, retryable vs non-retryable outcome, backoff or Retry-After wait, give up after the last attempt), with the full patch kept available in a `<details>` block rather than pasted inline in full.

FAIL if retryClient.ts is shown only as a raw diff, only described in one sentence with no pseudocode, or the pseudocode contradicts the code (for example says it never retries timeouts).
