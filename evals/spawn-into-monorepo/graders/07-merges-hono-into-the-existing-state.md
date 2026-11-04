---
type: llm
focus: trace
weight: 1
---

PASS if the run updates the existing bruhs:state block in both CLAUDE.md and AGENTS.md by merging: stack.frameworks (array) becomes Next.js plus Hono, stack.structure stays "monorepo", and the existing values survive: database drizzle-postgres, auth better-auth, tooling Turborepo and biome, and integrations.linear with the same team and project ids.

FAIL if the block is not updated, uses a singular stack.framework string, drops Next.js or any of the existing values, or only one of the two files is updated.
