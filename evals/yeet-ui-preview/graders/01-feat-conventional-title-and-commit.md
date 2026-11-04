---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin (with full commit messages) and every `gh pr create` (with title and body).

PASS if the PR title and every pushed commit subject are Conventional Commits of type `feat` describing the leaderboard (scope optional, for example `feat(game): add leaderboard sidebar`).

FAIL if no PR was created, or the PR title or a commit subject is not Conventional Commits or uses another type.
