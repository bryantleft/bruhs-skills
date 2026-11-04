---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` (and any `gh pr edit`) with the full PR body.

PASS if the body lists at least one risk, and every risk names a watch signal a reviewer could actually check, such as the `sms.opt_out`, `sms.send_suppressed` or `sms.duplicate_webhook` log events, a metric, or an error-tracker query.

FAIL if there are no risks, it says "No risks", a risk has no watch signal, or the risks section holds verification steps instead of risks.
