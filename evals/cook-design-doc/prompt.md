---
tags: [cook]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

/bruhs:cook move fleet balance reads off the primary db; the dashboard and the billing service both read them

Dashboard p95 went from 100 ms to 600 ms over the last six months as fleet_balances grew past 40M rows, and every dashboard load reads balances from the primary. If you need me to pick between approaches, go with your recommendation.
