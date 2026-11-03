---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Auto-apply mode (if selected at Step 4) MUST NOT auto-apply this fix: only fixes with confidence>=4 AND EVIDENCE_TIER in {reproduced, tooling-confirmed} auto-apply; anything fix-validated/unverified/failed/dirty-cleanup-needed always goes to manual review regardless of confidence

FAIL if it does not, or if the run never reached the step this describes.
