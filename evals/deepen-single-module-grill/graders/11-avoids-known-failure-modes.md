---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Re-runs a codebase-wide Phase 1 exploration despite --no-explore
- Designs one interface only
- Presents alternatives but refuses to pick a winner
- Adds a port (interface + adapter) for a dependency that has a single implementation
- Writes the TypeScript implementation of the new ReservationManager
- Stops to ask the user questions instead of making the calls, though the user said they would not be around
