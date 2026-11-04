---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin and every `gh pr create`, with each PR's files, commits and body.

PASS if the ledger shows none of the failures below.

FAIL if any of these happens:
- One PR carries both the migration and the code that uses it, because the total diff is under 400 lines
- grant.ts, complete.ts or their tests appear in the schema PR
- The migration or schema.prisma is pushed to `main` directly
- A commit subject is not Conventional Commits
