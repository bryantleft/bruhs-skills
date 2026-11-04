---
type: llm
focus: trace
weight: 1
---

PASS if every Phase 2 candidate has all of: Layer, Current state, Evidence (file paths, CI step names, thresholds or commit history), Bug class it would catch, Proposed adoption, Gating posture, Cross-layer effect, and Rough effort, and the list is ranked by bug class prevented and cross-layer leverage (the orchestrator fix near the top), not by effort.

FAIL if any candidate is missing a field, or the ranking is by effort.
