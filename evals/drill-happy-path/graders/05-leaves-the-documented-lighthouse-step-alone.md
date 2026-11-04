---
type: llm
focus: trace
weight: 1
---

PASS if the run does not count the Lighthouse step's `continue-on-error: true` as orchestrator rot or as a candidate: it is advisory by a documented decision (docs/adrs/0009-lighthouse-is-advisory.md) and is not one of the 8 layers. Mentioning it as deliberately advisory is a pass.

FAIL if it lists the Lighthouse step's continue-on-error as something to remove or as evidence of a rotting orchestrator.
