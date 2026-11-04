---
type: llm
focus: trace
weight: 1
---

PASS if the run designs at least three distinct gates (strict from day 1, ratchet-only, and a scoped pilot on one package such as app/billing), each with its own threshold, rollout shape and what breaks.

FAIL if it presents fewer than three, or alternatives without thresholds or what-breaks analysis.
