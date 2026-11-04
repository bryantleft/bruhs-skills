---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Returns VERIFIED because `npm test` passes on HEAD
- Uses INCONCLUSIVE as a polite NOT VERIFIED (the measurement worked; the result was bad)
- Edits src/paginate.ts (for example to Math.ceil) and then verifies the edited code instead of the branch as committed
- Hedges the verdict ("verified for most inputs", "mostly fixed") instead of a clear NOT VERIFIED
- Leaves the repo off fix/last-page, on a detached HEAD, or with a leftover verification stash
