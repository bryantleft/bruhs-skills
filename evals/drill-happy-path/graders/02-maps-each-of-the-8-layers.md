---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Maps each of the 8 layers to its current state (absent / advisory / gated / rotting). Calls out at minimum: acceptance specs ABSENT, mutation runner ABSENT, architecture checker ABSENT (ADR exists, enforcer doesn't), test-code linter ABSENT (tests/ excluded from lint), CI orchestrator ROTTING (typecheck in continue-on-error)

FAIL if it does not, or if the run never reached the step this describes.
