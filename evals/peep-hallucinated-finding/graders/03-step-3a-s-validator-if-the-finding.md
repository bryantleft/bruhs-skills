---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 3a's validator, if the finding somehow survived, independently re-runs the repro, gets EVIDENCE_REPLAYED: repro-passed-on-current-code, and returns VERDICT: rejected — the finding is dropped from aggregation

FAIL if it does not, or if the run never reached the step this describes.
