---
type: llm
focus: trace
weight: 1
---

PASS if the schema change for the new tables (referrals and referral_payouts, or equivalently named) is its own row or rows, holding only the migration under drizzle/ and the generated schema in src/db/schema.ts, and comes before every row that uses those tables.

FAIL if a table is created in the same row as the purchase-hook, payout or admin-page work, or the schema row comes after a row that depends on it.
