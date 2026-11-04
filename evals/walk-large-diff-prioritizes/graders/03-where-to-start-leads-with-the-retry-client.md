---
type: llm
focus: trace
weight: 1
---

PASS if "Where to start" (the reading order) begins with src/lib/retryClient.ts or src/lib/http.ts, and the import-only service files and tsconfig.json come after the core files or are marked skim-only.

FAIL if there is no reading order, or it starts with the service files or tsconfig.json.
