---
type: llm
focus: trace
weight: 1
---

PASS if the run makes no attempt at Linear: no search for or call to any Linear tool, no ticket creation or reuse, and no status update after the PR opens.

FAIL if it looks up, calls, or asks about Linear tools, or invents a ticket.
