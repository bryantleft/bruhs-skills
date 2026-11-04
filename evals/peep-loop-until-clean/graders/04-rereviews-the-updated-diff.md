---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: after the first push it reviews again, and the later pass concentrates on what changed since that push (the rewritten retry loop and anything still open) rather than re-litigating the whole diff from scratch.

FAIL if it reviews and fixes once and never re-reviews, or if the run never reached a second pass.
