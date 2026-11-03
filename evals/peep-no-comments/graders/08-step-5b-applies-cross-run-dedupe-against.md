---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5b applies cross-run dedupe against priorFindings — skips findings whose issue_key matches a prior entry with unchanged context_hash and user_action != 'applied'

FAIL if it does not, or if the run never reached the step this describes.
