---
type: llm
focus: trace
weight: 1
---

PASS if the doc's risks and rollout list only concerns that apply to this design, and those include the billing read-then-charge in src/billing/charge.ts (a replica lag or stale cache entry there lets billing charge against an old balance) and how to roll back.

FAIL if the risks miss the billing staleness concern, miss rollback, or pad the section with generic concerns or "N/A" lines. FAIL if no doc is written.
