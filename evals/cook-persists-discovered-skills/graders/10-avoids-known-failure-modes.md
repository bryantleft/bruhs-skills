---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Uses stripe-best-practices for this session but does NOT persist it, so the next session has to rediscover it
- Persists by writing .claude/bruhs.json (legacy path) instead of via sync_bruhs_block.py
- Updates state but skips re-deriving rules, leaving the rules block stale
- Writes the new skill into only CLAUDE.md, not AGENTS.md
- Drops, re-orders or de-duplicates the existing skills while persisting (e.g. drops superpowers because it's a 'plugin not a skill', or drops skills that weren't available this session)
- Asks the user to run /bruhs:claim to update the config instead of doing the write inline
