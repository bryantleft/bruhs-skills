---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` with its full title and body.

PASS if a PR was created with a Conventional Commits `feat` title, and its body follows yeet's PR shape (a summary that leads with the new leaderboard behavior, then testing) while either omitting the Linear section or marking it not applicable (for example "N/A, git-only mode"). It must not contain a ticket ID.

FAIL if no PR was created, the body has a Linear section with a placeholder like `<TICKET-ID>` or an invented ID, or the title isn't Conventional Commits.
