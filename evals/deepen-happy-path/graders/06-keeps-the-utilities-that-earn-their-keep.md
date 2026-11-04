---
type: llm
focus: trace
weight: 1
---

PASS if the run does not list money.ts or dates.ts as deepening candidates: deleting either would scatter real logic (zero-decimal currencies; month-end clamping) across their callers. Saying they earn their keep is a pass.

FAIL if either is presented as a shallow module to deepen or merge.
