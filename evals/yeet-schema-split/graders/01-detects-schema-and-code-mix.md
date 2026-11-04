---
type: llm
focus: trace
weight: 1
---

PASS if, before committing anything, the run notices that the diff mixes schema files (prisma/schema.prisma and the new prisma/migrations/20261103120000_add_reward_grants/migration.sql) with application code (src/rewards/grant.ts, src/purchases/complete.ts and their tests), and says the schema change has to ship in its own PR.

FAIL if it commits the mixed diff on one branch without remarking on it, or only notices after opening a PR.
