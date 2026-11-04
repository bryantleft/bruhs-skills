---
type: llm
focus: trace
weight: 1
---

PASS if the run reports what it auto-fixed with a count per category (unused imports, console.log removals, redundant type annotations) and how many issues remain for interactive fixing.

FAIL if it gives no per-category counts, or the counts contradict the edits it actually made.
