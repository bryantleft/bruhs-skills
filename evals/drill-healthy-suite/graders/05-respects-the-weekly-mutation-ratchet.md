---
type: llm
focus: trace
weight: 1
---

PASS if the run treats the weekly mutation run with a ratchet against mutants-baseline.json as a deliberate, documented posture (docs/adr/0003-weekly-mutation-ratchet.md) that meets drill's floor for that layer ("scheduled, with a ratchet-only gate"), and does not propose replacing it with a per-PR hard gate.

FAIL if it calls the mutation layer advisory-only or proposes a per-PR mutation gate as a candidate.
