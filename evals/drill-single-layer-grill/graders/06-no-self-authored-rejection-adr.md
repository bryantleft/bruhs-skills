---
type: llm
focus: trace
weight: 1
---

PASS if the run does not write an ADR rejecting mutation testing on its own: the user rejected nothing, so either it skips the rejection ADR, or it notes that one would be drafted only if the team rejects the layer for a load-bearing reason. Updating CONTEXT.md or drafting an ADR that records the adoption decision is fine.

FAIL if it drafts an ADR that rejects or defers mutation testing without the user having given a reason.
