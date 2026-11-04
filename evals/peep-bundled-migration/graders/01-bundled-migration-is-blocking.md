---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it raises a must-fix / `issue (blocking)` finding that PR #412 bundles a schema migration (drizzle/0007_add_index_orders_status.sql and drizzle/meta/_journal.json, plus the schema change) with application code (src/orders/list.ts), and cites the changed-file list from tool output (`git diff --name-only main...HEAD`, `gh pr diff 412 --name-only` or equivalent) as the evidence.

FAIL if it does not, or if the run never reached the step this describes.
