---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Exits with a one-line summary of what was migrated. Does NOT re-run stack detection (Steps 2–6) on a migrate path — the legacy JSON IS the source of truth

FAIL if it does not, or if the run never reached the step this describes.
