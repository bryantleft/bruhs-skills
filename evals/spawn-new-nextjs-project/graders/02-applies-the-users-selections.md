---
type: llm
focus: trace
weight: 1
---

PASS if the selections the run uses for my-app match what the user gave: single package (not a Turborepo monorepo), Web → TypeScript → Next.js, styling Tailwind CSS + shadcn/ui, tooling Biome, and no database, auth or state library; and it does not stop to ask about any of these again.

FAIL if any selection differs (e.g. a monorepo, Astro, ESLint instead of Biome, a database added), or the run ends asking the user about a choice they already made.
