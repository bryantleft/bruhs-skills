---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Writes an implementation manual (file-by-file steps) with no trade-offs or alternatives
- Opens the doc with the solution ('we will add Redis') instead of the problem
- Pads the doc with boilerplate sections marked N/A
- Draws a diagram with unlabelled arrows or arrows labelled 'uses'
- Proposes moving the shared getFleetBalance in src/balances/read.ts to a replica or cache without addressing that src/billing/charge.ts decides charges from it
- Starts coding before the doc is approved
