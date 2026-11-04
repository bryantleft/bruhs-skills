---
type: llm
focus: trace
weight: 1
---

PASS if every Phase 2 candidate has all of: Files, Problem, Proposed deepening, Benefits split into Leverage and Locality, Dependency category (in-process / local-substitutable / remote-owned / true-external; Stripe is true-external), and Rough effort (S/M/L). There are few candidates (roughly 1 to 4).

FAIL if any candidate is missing a field, the dependency category is wrong for Stripe, or the list is padded past the high-leverage ones (more than about 5).
