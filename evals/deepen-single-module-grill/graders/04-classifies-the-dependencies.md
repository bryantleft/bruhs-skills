---
type: llm
focus: trace
weight: 1
---

PASS if the run classifies Stripe (deposits) as a true-external dependency and the Drizzle/Postgres store as local-substitutable (PGlite in tests, per docs/adr/0001), and lets those categories decide how each is tested across the seam.

FAIL if it gives no dependency categories, or classifies Postgres as needing a mocked port or Stripe as in-process.
