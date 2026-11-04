---
type: llm
focus: trace
weight: 1
---

PASS if each candidate names the concrete bug class that slips through today with evidence from this repo (for example the dashboard page already importing @/marketing/PricingTable against ADR 0007; `expect(true).toBe(true)` in tests/checkout.test.ts and toBeDefined() in pricing.test.ts surviving without a mutation runner or test-code linter), and a layer with no concrete answer here (such as the complexity composite on this small, simple code) is left out or explicitly set aside.

FAIL if candidates rely on generic best practice with no evidence from the repo, or every absent layer is proposed regardless.
