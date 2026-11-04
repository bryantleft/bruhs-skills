---
type: llm
focus: trace
weight: 1
---

PASS if the run writes .github/workflows/ci.yml for obby-game whose steps run selene and stylua (e.g. `selene src` and `stylua --check src`, with the toolchain installed via Aftman as in the command doc's Luau / Rojo template), and that has no pnpm or Node steps.

FAIL if no workflow is written, it uses pnpm / Node steps, or it omits selene or stylua.
