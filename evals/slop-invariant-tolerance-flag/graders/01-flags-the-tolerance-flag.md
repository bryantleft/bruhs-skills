---
type: llm
focus: trace
weight: 1
---

PASS if the report flags `missingAccountAsZero` in src/ledger/reconcile.ts (and its use in nightly.ts) as tolerating a violated invariant at the read site: it hides ledgers that are missing required accounts from the check that found them, and treats failure as a zero balance. Citing bruhs's "fail loudly and actionably" principle (practices/engineering-principles.md) by name or substance is expected.

FAIL if the flag is not reported, or is reported only as a naming/style issue.
