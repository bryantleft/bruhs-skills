---
type: llm
focus: trace
weight: 1
---

PASS if the run writes a bruhs:state block to both CLAUDE.md and AGENTS.md (sync_bruhs_block.py or equivalent) containing the freshly detected stack (framework Next.js, database Drizzle/Postgres) and integrations.linear.mcpServer "linear-sonner", plus a bruhs:rules block derived from it.

FAIL if either file lacks the state block, or the written stack says Astro or Convex.
