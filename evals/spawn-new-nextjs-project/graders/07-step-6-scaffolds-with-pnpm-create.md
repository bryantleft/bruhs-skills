---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 6 scaffolds with `pnpm create next-app@latest my-app` and initializes shadcn without hard-coding flags: uses the shadcn skill/MCP if available, otherwise checks `pnpm dlx shadcn@latest init --help` and runs init with the current flags for the mira preset + CSS variables

FAIL if it does not, or if the run never reached the step this describes.
