---
type: llm
focus: trace
weight: 1
---

PASS if the report says the backfill has to run before (or in the same deploy as) removing the flag, because otherwise the nightly reconciliation starts failing on every old ledger that has no accounts.

FAIL if it gives no ordering, or suggests removing the flag first.
