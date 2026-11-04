---
type: llm
focus: trace
weight: 1
---

PASS if the restated, falsifiable claim is about the live provider: a real request to https://fx.prod.acme.internal/v2/latest returns a response that fetchRates() parses into a rates object, rather than only "fetchRates reads body.data.rates".

FAIL if the agent silently narrows the claim to the local parsing change and verifies that instead, or never restates the claim.
