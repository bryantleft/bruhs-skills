---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin and every `gh pr create` and `gh pr edit`, each PR with its head, base, files, commits and body.

PASS if three PRs were opened, one per subject, in dependency order: first the schema PR (only prisma/schema.prisma and the reward_grants migration), then the logic PR (src/rewards/* and src/purchases/complete.ts with their tests), then the UI PR (src/app/settings/rewards-panel.tsx, rewards-panel.module.css, page.tsx).

FAIL if there are fewer than three PRs, any PR mixes subjects (for example the migration with grant.ts, or the panel with the logic), or the order differs.
