---
type: llm
focus: trace
weight: 1
---

PASS if the run checks whether anything dispatches on RewardGranted (for example a grep for `instanceof` or a class-keyed map, finding none; Ledger.post() keys on event.type and already rejects non-positive amounts) and then recommends dropping the subclass in favour of `new LedgerEvent({ type: LedgerEventType.RewardGranted, ... })` at the call sites.

FAIL if it keeps RewardGranted, or recommends removing it without checking for class-based dispatch.
