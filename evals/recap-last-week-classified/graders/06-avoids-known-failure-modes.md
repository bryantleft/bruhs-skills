---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Bullets describe motivation or impact the commits don't show ("greatly improved the shopping experience") instead of what changed in the system
- Bullets describe files moved rather than behavior ("edited src/cart.ts")
- Uses the whole team's history (--all-authors behavior) when the user didn't ask for it
- Summarizes uncommitted or staged work
- Writes or commits any file in the repo
