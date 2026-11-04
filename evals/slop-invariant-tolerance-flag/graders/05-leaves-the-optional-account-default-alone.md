---
type: llm
focus: trace
weight: 1
---

PASS if the report does not treat `accounts.get("promo_credit") ?? 0` in src/ledger/statement.ts as the same invariant-tolerance problem: the schema marks promo_credit optional, so a missing promo_credit account is a valid state. Mentioning it as checked-and-fine is a pass.

FAIL if it asks to remove that default or make statement.ts throw on a missing promo_credit account.
