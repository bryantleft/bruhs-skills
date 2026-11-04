---
type: llm
focus: trace
weight: 1
---

PASS if the doc's problem section states the evidence with numbers (dashboard p95 went from 100 ms to 600 ms over six months as fleet_balances grew past 40M rows), says who is hurt (dashboard users on every page load, and billing as the other reader), and says why now, without proposing a solution inside the problem section.

FAIL if the problem section uses adjectives instead of the numbers, leaves out who is hurt or why now, or opens with the fix ("we will add a replica/cache"). FAIL if no doc is written.
