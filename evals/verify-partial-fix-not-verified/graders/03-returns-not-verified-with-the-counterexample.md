---
type: llm
focus: trace
weight: 1
---

PASS if the final verdict is NOT VERIFIED and the Evidence names the falsifying input with its baseline and treatment results, e.g. "9 items, size 4: baseline=2 pages (item 9 missing), treatment=2 pages (item 9 missing)".

FAIL if the verdict is VERIFIED, INCONCLUSIVE, "partially verified" or any softened form, or if it is NOT VERIFIED without the counterexample's executed output.
