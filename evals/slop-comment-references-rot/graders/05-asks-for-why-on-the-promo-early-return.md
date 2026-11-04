---
type: llm
focus: trace
weight: 1
---

PASS if the run points at `if (req.kind === "promo") return;` in grantReward() as a branch that bypasses eventsFor()'s promo case, and asks for or adds a one-line comment naming the constraint (promo grants are posted by the nightly promo batch in src/jobs/promo-batch.ts, so granting here would double-credit). Asking the author for the reason, without guessing, also passes.

FAIL if it says nothing about this branch, suggests deleting it as dead code, or proposes a multi-line comment.
