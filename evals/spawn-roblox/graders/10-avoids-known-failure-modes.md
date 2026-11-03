---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Offers TypeScript-specific options (Tailwind, shadcn, Vitest) on a Roblox project
- Runs `pnpm create` instead of `rojo init` for scaffolding
- Includes integrations.linear in the config with empty/null values instead of omitting it
