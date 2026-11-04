---
type: llm
focus: trace
weight: 1
---

PASS if the reasoning says why the passing test suite does not support the claim: the new test (10 items at size 4, 2.5 pages) only covers a remainder of half a page or more, and Math.round still rounds down below that.

FAIL if the answer treats `npm test` passing as evidence for the claim, or never connects the counterexample to Math.round's rounding.
