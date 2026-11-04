---
type: llm
focus: trace
weight: 1
---

PASS if the stack the run detects and reports is a single-package Hono API: framework Hono (from package.json), libraries including zod, testing vitest (vitest.config.ts), tooling Biome (biome.json); Docker as infra also counts. Naming variants count.

FAIL if it reports a framework other than Hono (e.g. Next.js), structure monorepo, or a linter other than Biome.
