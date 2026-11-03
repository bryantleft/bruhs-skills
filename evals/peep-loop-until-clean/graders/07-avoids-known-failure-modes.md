---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats --loop as requiring an external bot (posts '@greptile review' / waits on a bot) when none is installed, instead of running the agent's own review
- Single-pass: reviews and fixes once but never re-reviews the updated diff
- Loops forever / ignores the max-iterations cap and the no-progress guard
- Applies a cosmetic 'fix' to make a finding disappear (appeasement) instead of declining an unreproducible one
- Re-litigates the whole diff every iteration (no convergence / no dedupe), or pushes code that fails validation to keep looping
