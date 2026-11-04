---
type: llm
focus: trace
weight: 1
---

PASS if, before writing any code, the run decides this change needs a design doc and names at least two of the triggers from practices/design-docs.md that apply here: another team depends on the result (billing, which owns src/billing/ per .github/CODEOWNERS, reads balances too), a hard-to-reverse storage choice (read replica, cache, or a materialized table), the right design is unclear, or money is at stake (billing charges against the balance it reads).

FAIL if it plans in chat or starts building without a design doc, or decides on a doc without saying which triggers apply.
