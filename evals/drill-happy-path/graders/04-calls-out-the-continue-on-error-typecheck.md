---
type: llm
focus: trace
weight: 1
---

PASS if the run states explicitly that `continue-on-error: true` on the Typecheck step makes typecheck advisory regardless of intent, and notes the "Temporary" commit that added it.

FAIL if it does not call this out.
