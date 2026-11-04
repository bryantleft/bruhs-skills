---
type: llm
focus: trace
weight: 1
---

PASS if the report recommends both backfilling the required accounts for existing ledgers that lack them and then removing `missingAccountAsZero`, so reconcile() keeps failing loudly on any ledger that still violates the invariant.

FAIL if it omits the backfill, or keeps the flag in place as the long-term answer.
