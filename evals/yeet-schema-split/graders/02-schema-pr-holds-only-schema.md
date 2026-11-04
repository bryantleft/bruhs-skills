---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin and every `gh pr create`, each PR with its head, base, files and full body.

PASS if one PR targets `main` and its files are exactly prisma/schema.prisma and prisma/migrations/20261103120000_add_reward_grants/migration.sql (nothing under src/).

FAIL if there is no such PR, if the schema PR includes any file under src/, or if all the work went into one PR.
