---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` (and any `gh pr edit`) with the full PR body and the commit messages.

PASS if the final PR body never cites a plan requirement ID such as "R4" (or R1-R5) without a link to the plan, and instead states the rule itself (for example "Twilio can deliver the same webhook twice; a repeat is ignored").

FAIL if the body says "R4", "per R4", "covers R1-R5" or similar without a link.
