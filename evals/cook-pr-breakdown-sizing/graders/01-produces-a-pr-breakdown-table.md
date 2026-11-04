---
type: llm
focus: trace
weight: 1
---

PASS if the plan (in chat, or in a design doc's appendix if the run writes one) includes a PR breakdown table with one row per PR, a depends-on column, and a rough size per row in estimated reviewable lines.

FAIL if there is no breakdown, it is a prose list, or it lacks the dependency column or per-row sizes.
