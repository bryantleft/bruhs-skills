---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Scaffolds the Hono app at the repo root instead of apps/api
- Overwrites the existing bruhs:state block in CLAUDE.md instead of merging the new app into the monorepo config
- Uses `stack.framework` (singular string) in the monorepo config instead of `stack.frameworks` (array)
