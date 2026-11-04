---
type: llm
focus: trace
weight: 1
---

PASS if the run picks one design (or a stated hybrid) and the recommendation fits the 10-minute cap: for example a scheduled (nightly/weekly) full run with a ratchet, or a per-PR run limited to changed lines or one package whose runtime it estimates against the cap (using the ~22-second suite and ~4-minute job). It names the trade-off of its choice.

FAIL if it leaves the choice to the user, or recommends full per-PR mutation runs without confronting the 10-minute budget.
