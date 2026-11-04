---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: after applying fixes and before committing, it runs the project's full check suite (`npm run typecheck`, `npm run lint` and `npm test`, or the equivalent package.json scripts) on the combined changes, not only the per-fix checks.

FAIL if it does not, or if the run never reached the step this describes.
