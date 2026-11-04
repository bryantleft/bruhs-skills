---
type: llm
focus: trace
weight: 1
---

PASS if the run does not flag '// TODO(ENG-123): cap referral grants per sponsor once the fraud rules land' as a rotting reference or as something to remove: a TODO that tracks open work with a ticket is fine.

FAIL if it lists the TODO(ENG-123) comment among the references to remove or rewrite.
