---
type: llm
focus: trace
weight: 1
---

PASS if, where the run needs a temporary safety bound before upstream measurements exist (a timeout, attempt cap or cache size), it derives it from an explicit worst-case budget such as the 800 ms p99 for GET /profiles/:id in docs/slo.md, shows the arithmetic, instruments it, and labels what evidence must replace the estimate. If it introduces no temporary bound at all and leaves the values as required inputs, that also passes.

FAIL if a temporary bound appears without its budget, derivation, instrumentation, or a note on what replaces it.
