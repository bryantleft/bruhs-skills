---
type: llm
focus: trace
weight: 1
---

PASS if the run reads practices/engineering-principles.md before it plans the retry and cache design.

FAIL if it plans or writes code first and reads the file later, or never reads it.
