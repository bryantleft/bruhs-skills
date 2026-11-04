---
type: llm
focus: trace
weight: 1
---

PASS if the 22 src/services/*.ts files, whose only change is the import path ("../lib/http.ts" to "@/lib/http.ts"), are grouped together as mechanical (import-only) changes in a collapsed `<details>` block or a single summarizing line, with the count or a clear group description.

FAIL if the walkthrough gives individual core-change sections to service files, or omits the codemod entirely so a reviewer can't tell what happened to those 22 files.
