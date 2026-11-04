---
type: llm
focus: trace
weight: 1
---

PASS if the recap states the resolved absolute range as a YYYY-MM-DD date (or dates) ending on the day before the run's current date, with today excluded. Use the dates in the agent's own commands (for example `date` output or the --since/--until values) to check.

FAIL if no absolute date is shown, or the range includes today.
