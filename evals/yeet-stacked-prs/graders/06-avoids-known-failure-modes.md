---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Opens three PRs all targeting main so each diff includes the layers below
- Puts the migration in the same PR as the code that uses it
- Slices by file count or commit time instead of subject
