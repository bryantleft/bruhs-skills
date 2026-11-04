---
type: llm
focus: trace
weight: 1
---

PASS if, because it's unsettled whether payouts are computed at purchase time (in the onPurchaseCompleted hooks in src/purchases/hooks.ts) or by a nightly job (src/jobs/nightly.ts), the run recommends a throwaway end-to-end spike on a local branch first to learn the seams, and treats the breakdown as provisional until the spike has settled that question.

FAIL if it picks the payout timing without acknowledging the uncertainty, or treats the breakdown as final without a spike.
