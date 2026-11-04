---
type: llm
focus: trace
weight: 1
---

PASS if the stack the run detects and reports for this repo is: structure single (no turbo.json or pnpm-workspace.yaml), framework Next.js (next.config.ts), styling Tailwind CSS (tailwind.config.ts) and shadcn/ui (components/ui/), database Drizzle with Postgres (drizzle.config.ts), and Biome as tooling (biome.json). Naming variants count (e.g. "nextjs", "tailwind", "drizzle-postgres").

FAIL if any of these is missing or wrong, for example structure monorepo, or a linter other than Biome.
