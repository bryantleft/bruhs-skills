---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Loads stripe-best-practices for this session but does NOT persist it — next session has to rediscover it
- Persists by writing .claude/bruhs.json (legacy path) instead of via sync_bruhs_block.py — defeats the migration
- Updates state but skips re-deriving rules — leaves the rules block stale
- Writes the new skill into only CLAUDE.md, not AGENTS.md — breaks the mirror invariant
- Re-orders or de-duplicates the existing skills list incorrectly while persisting (e.g. drops superpowers because it's a 'plugin not a skill')
- Asks the user to manually run /bruhs:claim to update the config instead of doing the write inline
