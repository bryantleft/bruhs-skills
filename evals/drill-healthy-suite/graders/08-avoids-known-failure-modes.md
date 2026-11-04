---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Pads the list with 3+ candidates despite the suite being healthy
- Misses that the complexity composite is the one absent layer because every other layer looks good
- Proposes specific tools (for example a particular complexity or CRAP tool) in Phase 2 instead of staying tool-agnostic
