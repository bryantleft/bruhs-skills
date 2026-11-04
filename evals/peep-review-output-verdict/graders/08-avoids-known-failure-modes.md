---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- States a verdict against the original head SHA after the head moved, or never checks whether it moved
- Reports a finding without a validation note
- Surfaces a generic "behind main / rebase" nit
- Posts a review, comment or approval to the PR although the user asked to keep it local
