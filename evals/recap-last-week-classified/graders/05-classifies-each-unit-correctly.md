---
type: llm
focus: trace
weight: 1
---

PASS if the Classification puts the fuzzy search work (SHOP-210) under net-new, the cart re-add fix (SHOP-214) and the per-line tax rounding fix (SHOP-219) under bugfix, and the zod bump and the orders.ts split under tech debt.

FAIL if any of those units lands in the wrong bucket, or the classification is too vague to tell (for example "a mix of work").
