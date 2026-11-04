---
type: llm
focus: trace
weight: 1
---

PASS if the run drafts an ADR (in its reply or as a file such as docs/adr/0002-...md) recording that deposits stay in the same module and transaction as their reservation, and that a separate deposit service was tried and rejected for that reason, so it is not re-suggested.

FAIL if it does not draft the ADR, or proposes a separate deposit service anyway.
