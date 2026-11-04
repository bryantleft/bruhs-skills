---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats the 40% total-line coverage gate as gated instead of below the floor
- Misses the continue-on-error: true on Typecheck and reports the CI orchestrator as healthy
- Treats the unenforced ADR 0007 as "architecture checker present"
- Trusts green CI as evidence that the suite is safe
