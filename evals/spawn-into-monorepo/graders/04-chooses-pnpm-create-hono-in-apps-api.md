---
type: llm
focus: trace
weight: 1
---

PASS if the scaffold command the run chooses is `pnpm create hono@latest apps/api` (extra flags such as a template or package-manager flag are fine), run from the monorepo root.

FAIL if it scaffolds with npm, npx, yarn or bun, targets the repo root or another path, or runs it from inside apps/.
