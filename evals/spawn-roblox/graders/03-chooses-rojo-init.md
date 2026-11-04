---
type: llm
focus: trace
weight: 1
---

PASS if the scaffold command the run chooses is `rojo init obby-game` (or `rojo init` inside a new obby-game directory).

FAIL if it scaffolds with pnpm create, npm, npx or another non-Rojo tool, or never attempts the Rojo scaffold.
