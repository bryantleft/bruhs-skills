---
type: llm
focus: trace
weight: 1
---

PASS if, by the end of the run, pnpm-workspace.yaml includes apps/api (an "apps/api" entry, or "apps/web" replaced by "apps/*"), so the new app is part of the workspace. The file originally listed only "apps/web" and "packages/*". turbo.json's generic tasks already cover new apps, so leaving turbo.json unchanged is fine.

FAIL if pnpm-workspace.yaml still lists only apps/web and packages/*, or the run claims it updated the workspace when it did not.
