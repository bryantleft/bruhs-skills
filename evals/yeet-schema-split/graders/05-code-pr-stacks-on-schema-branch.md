---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin and every `gh pr create`, each PR with its head, base and files.

PASS if a second PR's base is the schema PR's branch (not `main`), and its files are the application code and tests (src/rewards/grant.ts, src/rewards/grant.test.ts, src/purchases/complete.ts, src/purchases/complete.test.ts) without the migration or schema.prisma.

FAIL if there is no second PR, it targets `main` (so its diff would include the schema), or it contains schema or migration files.
