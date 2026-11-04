---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats "packages/store" as a freeform prompt and generates a diagram without reading the files
- Puts external dependencies inside the module frame instead of a separate External frame
- Draws the dependents (packages/ui, apps/web) as if they were part of the module
- Claims a render or upload succeeded that did not happen
