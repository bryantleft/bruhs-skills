---
type: llm
focus: trace
weight: 1
---

PASS if the plan (in chat, or in a design doc if the run writes one) lists CSV export of balances as a non-goal, a decided exclusion, kept separate from any deferred items (deferrals say when they come back; a non-goal doesn't).

FAIL if CSV export is missing from the plan, is listed as "later"/"phase 2"/a deferral, or the plan extends src/balances/export-csv.ts to partner admins.
