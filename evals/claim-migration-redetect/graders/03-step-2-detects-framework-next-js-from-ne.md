---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 2 detects framework='Next.js' from next.config.ts — does NOT carry forward the stale framework='Astro' from the legacy JSON

FAIL if it does not, or if the run never reached the step this describes.
