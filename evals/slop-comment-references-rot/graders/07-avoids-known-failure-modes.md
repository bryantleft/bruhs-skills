---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Leaves ticket/plan IDs in code comments because they look like useful context
- Keeps RewardGranted because the sibling RewardReversed on main follows the same pattern
- Deletes or discourages the why on the promo early return, or flags it as over-commenting
- Reports findings in code this branch did not add (for example asks to change RewardReversed or ledger.ts) as if they were this branch's slop, instead of at most noting them as follow-ups
