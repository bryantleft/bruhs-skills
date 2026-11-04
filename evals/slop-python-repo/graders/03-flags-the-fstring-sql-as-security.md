---
type: llm
focus: trace
weight: 1
---

PASS if the report flags the f-string query in search_products() in app/routes/products.py (`... WHERE name LIKE '%{q}%'`) as SQL injection, ranks it as a security issue at the top of the report (P2 / Critical), and recommends a bound parameter (for example `LIKE ?` with `f"%{q}%"` passed as the parameter).

FAIL if it is missing, or ranked below performance or style findings.
