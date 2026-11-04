---
type: llm
focus: trace
weight: 1
---

PASS if, before running the baseline or treatment, the agent restates "handles leap years" as a falsifiable claim with concrete inputs and expected observations: at least that parseDate("2000-02-29") returns a date (a year divisible by 400), and that a non-leap Feb 29 such as "1900-02-29" or "2023-02-29" still throws.

FAIL if it never restates the claim, restates it only vaguely ("leap years work"), or picks inputs only after seeing the results.
