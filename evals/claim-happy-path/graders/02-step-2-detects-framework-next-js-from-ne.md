---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 2 detects framework=Next.js (from next.config.ts), styling=['Tailwind CSS','shadcn/ui'] (tailwind.config + components/ui/), database=['drizzle-postgres'] (drizzle.config), tooling=['biome']

FAIL if it does not, or if the run never reached the step this describes.
