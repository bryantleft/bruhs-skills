---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` (and any `gh pr edit`) with the full PR body.

PASS if, under the template's `## Test plan` heading (not a new heading), the body has **Ran**, **Mutation-checked** and **Not tested** lines, and Not tested is filled with something real (for example: never sent against a real or staging Twilio number, or no concurrent duplicate deliveries). Mutation-checked may honestly say `none`.

FAIL if any of the three lines is missing, they sit under a new heading, or Not tested is empty or "N/A".
