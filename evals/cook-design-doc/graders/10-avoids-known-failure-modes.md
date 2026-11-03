---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Writes an implementation manual (file-by-file steps) with no trade-offs or alternatives
- Opens with the solution ('we will add Redis') instead of the problem
- Pads the doc with boilerplate sections marked N/A
- Draws a diagram with unlabelled arrows or arrows labelled 'uses'
- Starts coding before the doc is approved
