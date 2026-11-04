---
type: llm
focus: trace
weight: 1
---

PASS if the recap states the resolved absolute range for "last 3 days" as YYYY-MM-DD dates running from 4 days before the run's current date to today (the command's "last N days → N+1 days ago → now" row). Use the dates in the agent's own commands (for example `date` output or the --since value) to check.

FAIL if no absolute range is shown, or it is a different window.
