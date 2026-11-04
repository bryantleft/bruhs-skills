---
type: llm
focus: trace
weight: 1
---

PASS if the doc's goals are measurable outcomes (for example a dashboard p95 target at a stated load multiple, or billing never charging against a stale balance) rather than implementation steps, and it lists non-goals: things that could reasonably be goals but are excluded.

FAIL if goals are implementation tasks ("add a replica"), have no number or testable condition, or non-goals are missing. FAIL if no doc is written.
