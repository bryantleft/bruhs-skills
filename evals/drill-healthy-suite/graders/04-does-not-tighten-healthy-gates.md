---
type: llm
focus: trace
weight: 1
---

PASS if the run does not recommend raising the 85% changed-line coverage gate (or tightening other healthy gates) unless it names a concrete bug class the higher threshold would catch.

FAIL if it recommends raising coverage to 90% / 95% or similar without a concrete failure case.
