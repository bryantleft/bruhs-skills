---
type: llm
focus: trace
weight: 1
---

PASS if the recap states the resolved absolute date range for "last week" as YYYY-MM-DD dates running from 8 days before the run's current date to 1 day before it (today excluded), as the command's window table defines. Use the dates the agent's own commands show (for example `date` output or the --since/--until values) to check.

FAIL if no absolute range is shown, only "last week" is printed, or the range includes today.
