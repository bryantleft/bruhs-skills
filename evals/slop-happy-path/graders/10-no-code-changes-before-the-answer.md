---
type: llm
focus: trace
weight: 1
---

PASS if the run edits no file under src/ before the user answers: the `any`, the effect and the style object are reported, not changed.

FAIL if it edits any of these files (rewriting the `any`, removing the useEffect, hoisting the style object, or other edits) during this run.
