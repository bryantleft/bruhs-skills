---
type: llm
focus: trace
weight: 1
---

PASS if the run skips drill's Phase 1 walk and Phase 2 candidate list and starts grilling the mutation runner layer. Reading CONTEXT.md, the CI workflow, pyproject.toml and a few tests to frame the layer is expected and does not count as Phase 1.

FAIL if it maps all 8 layers, presents a candidate list, or asks which layer to grill.
