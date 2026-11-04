---
type: llm
focus: trace
weight: 1
---

PASS if the plan states how fleet ids a partner admin submits are scoped to their own tenant on the server: the tenant comes from session.tenantId (never from the request), and each requested fleet id is checked against fleets.tenantId (or the query joins fleets on it), with what happens to ids from another tenant (rejected with an error, not silently dropped or returned).

FAIL if the plan trusts request fleet ids the way postBalances does, filters only in the UI, or never mentions tenant scoping.
