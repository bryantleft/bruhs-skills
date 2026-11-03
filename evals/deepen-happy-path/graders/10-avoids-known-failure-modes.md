---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Runs a static analyzer (ts-prune / madge / eslint) instead of reading the code
- Skips the deletion test and promotes every thin wrapper as a candidate without justifying why each earns its keep
- Uses generic 'BillingService' / 'PaymentManager' language instead of the domain vocabulary in CONTEXT.md
- Substitutes 'component' or 'boundary' for 'module' / 'seam' — drifts away from the deepen vocabulary
- Returns 12+ candidates without filtering — failure to re-apply the deletion test
- Writes actual refactor patches in Phase 2 instead of staying decision-only
- Produces interface designs in Phase 2 instead of waiting for Phase 3 grilling
