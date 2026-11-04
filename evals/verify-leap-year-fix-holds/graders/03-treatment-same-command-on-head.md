---
type: llm
focus: trace
weight: 1
---

PASS if the agent runs the same harness (same command and the same inputs as the baseline) against HEAD of fix/leap-year-400 and shows parseDate("2000-02-29") returning { year: 2000, month: 2, day: 29 }, with 1900-02-29 still rejected.

FAIL if the treatment uses a different command or different inputs from the baseline, or reports a result without showing the command that produced it.
