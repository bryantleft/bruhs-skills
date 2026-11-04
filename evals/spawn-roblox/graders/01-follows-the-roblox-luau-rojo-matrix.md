---
type: llm
focus: trace
weight: 1
---

PASS if the run sets the project up as Type Roblox → Language Luau → Framework Rojo, per the command doc's matrix, and the stack it uses has only Luau-relevant choices: tooling Selene, StyLua and Rojo, and no TypeScript-only additions (no Tailwind, shadcn/ui, Zod, Vitest, Biome, Husky or Vercel).

FAIL if it picks another language or framework, or adds or proposes any TypeScript-only option for this project.
