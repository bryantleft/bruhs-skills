---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: the per-thread results use the structured format with an EVIDENCE_TIER (alongside REPRO_TEST / REPRO_COMMANDS / RED_OUTPUT / GREEN_OUTPUT where relevant), with the queries.ts must-fix at `reproduced`, the leaderboard-card suggestions (no bug claim) at `fix-validated` or similar non-reproduced tier, and the polling question at `n/a`.

FAIL if it does not, or if the run never reached the step this describes.
