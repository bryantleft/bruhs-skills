---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it appends each finding it showed to `.claude/.peep-history/PR-73.jsonl` as one JSON object per line (with fields such as issue_key, context_hash, user_action, validator_verdict and evidence_tier), and makes sure `.claude/.peep-history/` is listed in .gitignore.

FAIL if it does not, or if the run never reached the step this describes.
