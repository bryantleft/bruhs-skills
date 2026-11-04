---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` (and any `gh pr edit`) with the full PR body.

PASS if a PR was created and its final body avoids every failure below.

FAIL if any of these happens:
- Narrates the diff ("the handler reads X then calls Y")
- Packs the three cases into one comma or semicolon sentence
- Writes the body in lowercase chat style
- Lists verification steps under risks, or writes "No risks"
- Ticks the "Tested against a staging Twilio number" box, which never happened
