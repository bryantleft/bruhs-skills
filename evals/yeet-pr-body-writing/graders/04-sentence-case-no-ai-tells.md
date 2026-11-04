---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` (and any `gh pr edit`) with the full PR body.

PASS if the final body is in sentence case (labels included) and has none of these: em-dash chains (several em dashes in one paragraph, or stacked mid-sentence), parallel triads ("cleaner, safer, faster"), "This ensures..." or "This allows..." closings, rhetorical-question openers, or chatbot signoffs ("Let me know if...", "Happy to...").

FAIL if the body is lowercase chat style or Title Case labels, or contains any of the tells above.
