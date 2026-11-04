---
type: llm
focus: trace
weight: 1
---

PASS if the run reads CONTEXT.md before forming candidates, then reads code along at least two materially different call paths into src/billing (for example a request in src/api/checkout.ts or upgrade.ts, and a job in src/jobs/renewals.ts or retry-failed.ts).

FAIL if it never reads CONTEXT.md, reads only the files inside src/billing, or relies on a static analyzer (madge, ts-prune, eslint, dependency-cruiser) instead of reading.
