---
type: llm
focus: trace
weight: 1
---

PASS if the selections the run uses for the new app are Type API → Language TypeScript → Framework Hono, with Zod and no database or auth of its own, located at apps/api, without stopping to ask about any of these again.

FAIL if the framework, language or location differs (e.g. FastAPI, the repo root, packages/api), or the run ends asking about a choice the user already made.
