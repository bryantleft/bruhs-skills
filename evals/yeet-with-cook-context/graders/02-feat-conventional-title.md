---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push (with full commit messages) and every `gh pr create` (title and body).

PASS if the PR title and the commit subject are Conventional Commits of type `feat` describing the dark mode toggle (for example `feat: add dark mode toggle to settings page` or `feat(settings): ...`), under 70 characters, with no ticket ID in either.

FAIL if no PR was created, a title is not Conventional Commits or not `feat`, it runs over 70 characters, or it carries `PERDIX-145`.
