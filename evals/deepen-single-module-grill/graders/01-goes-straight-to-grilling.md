---
type: llm
focus: trace
weight: 1
---

PASS if the run skips deepen's Phase 1 walk and Phase 2 candidate list and starts grilling ReservationManager directly. Reading ReservationManager.ts, its repository, its three callers, their tests and CONTEXT.md to frame the problem is expected and does not count as Phase 1.

FAIL if it walks the wider codebase for other candidates, presents a Phase 2 candidate list, or asks which module to grill.
