---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin (with the branch name) and every PR the agent opened.

PASS if the work was pushed to a new branch named `<type>/<short-description>` with type `feat`, describing the leaderboard (for example `feat/add-leaderboard` or `feat/game-leaderboard`), and the PR was opened from that branch into `main`.

FAIL if nothing was pushed, the work was pushed to `main`, or the branch name doesn't follow `feat/<short-description>` (for example a ticket-style `perdix-123-...` name or a bare `leaderboard`).
