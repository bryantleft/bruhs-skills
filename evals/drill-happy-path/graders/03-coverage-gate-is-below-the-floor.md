---
type: llm
focus: trace
weight: 1
---

PASS if the run says the coverage gate does not meet the discipline floor: it measures 40% of total lines rather than changed lines, excludes every .tsx file and src/components/**, and its threshold was lowered 60 -> 50 -> 40 to keep CI green (threshold drift). Calling it effectively absent or rotting both pass.

FAIL if it calls the coverage layer "gated" or "partially gated" without these caveats, or misses that it is on total lines.
