---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Offers or adds TypeScript-specific options (Tailwind, shadcn, Vitest, Biome) to the Roblox project
- Runs `pnpm create` or another JS scaffolder instead of `rojo init`
- Writes integrations.linear with empty or null values instead of omitting it
- Says the game was scaffolded by rojo, or that CI passes, when that never happened
