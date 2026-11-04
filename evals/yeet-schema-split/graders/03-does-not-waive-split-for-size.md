---
type: llm
focus: trace
weight: 1
---

PASS if the run treats the split as required, not optional, and carries it out (as the user asked it to act on its recommendation), without arguing it away because the diff is small (about 120 lines, under the 400-line guideline) or the table is tiny.

FAIL if it ships one PR on the grounds that the change is small, offers the split only as an optional nicety, or stops to ask whether to split although the user said not to wait.
