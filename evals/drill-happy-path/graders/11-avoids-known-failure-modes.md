---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats the 40% total-line coverage gate as 'gated' instead of effectively absent (fails to apply the discipline-floor rule)
- Misses the continue-on-error: true on typecheck and reports CI orchestrator as healthy
- Proposes Stryker / Mutmut / specific test libraries in Phase 2 instead of staying tool-agnostic
- Invents new layer names ('integration tests', 'e2e suite') instead of mapping into the 8-layer vocabulary
- Flags layers (e.g. mutation runner) without a concrete 'what would slip through today' answer
- Writes the actual CI yaml or installs runner packages in Phase 1 / 2
- Treats the unenforced ADR (0007-app-must-not-import-from-marketing.md) as 'architecture checker present' — the rule isn't machine-checked
