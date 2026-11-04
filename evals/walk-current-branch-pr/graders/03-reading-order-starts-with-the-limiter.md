---
type: llm
focus: trace
weight: 1
---

PASS if the "Where to start" reading order puts src/middleware/rateLimit.ts (or its wiring in src/server.ts) first, and does not send the reviewer to package-lock.json, package.json or src/api.gen.ts before the core files.

FAIL if there is no reading order, or it leads with mechanical files.
