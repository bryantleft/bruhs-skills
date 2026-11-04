---
type: llm
focus: trace
weight: 1
---

PASS if the scaffold command the run chooses for the app is `pnpm create next-app@latest my-app` (extra flags such as --ts, --tailwind, --app or --src-dir are fine), run from the workspace.

FAIL if it scaffolds with npm, npx, yarn or bun (e.g. `npx create-next-app`), or skips the official CLI and hand-writes a Next.js project while presenting it as the scaffold.
