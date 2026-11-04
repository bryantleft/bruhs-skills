---
type: llm
focus: trace
weight: 1
---

PASS if, before designing alternatives, the run frames the layer with: the bug class (tests that run code but assert nothing meaningful, citing INC-41 and/or tests like tests/accounts/test_settings.py), the constraint (the 10-minute cap on the `checks` job), an illustrative gate failure message (for example "kill ratio on changed lines is 42%, gate is 70%"), and whether the gate starts hard or advisory-then-baseline.

FAIL if any of the four is missing, or the framing ignores the 10-minute cap.
