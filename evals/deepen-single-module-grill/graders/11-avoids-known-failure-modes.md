---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Re-runs Phase 1 exploration despite --no-explore
- Designs ONE interface only — violates the 'design-it-twice' rule (Phase 3b)
- Presents alternatives but refuses to pick a winner — 'recommending without an opinion is failure' (Phase 3c)
- Adds a port (interface + adapter) for a single implementation, violating 'two adapters means a real seam'
- Writes the actual TypeScript implementation of ReservationManager v2
- Skips the hand-off bundle (Phase 3e) — produces an interface design with no implementation plan, test plan, or tests-to-delete list
- Refuses to draft an ADR even when a load-bearing rejection reason would justify one
