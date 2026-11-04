---
type: llm
focus: trace
weight: 1
---

PASS if the run gives a state for each of the 8 layers (acceptance specs, unit tests, coverage gate, mutation runner, complexity composite, architecture checker, test-code linter, CI orchestrator) and gets these right: acceptance specs absent, mutation runner absent, architecture checker absent (ADR 0007 exists but nothing enforces it), test-code linter absent (eslint ignores tests/), CI orchestrator advisory/rotting (Typecheck runs with continue-on-error: true).

FAIL if a layer is missing from the map, or any of the five states above is wrong (for example the orchestrator called healthy, or the ADR counted as an architecture checker).
