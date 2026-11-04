---
type: llm
focus: trace
weight: 1
---

PASS if Phase 2 has at most two candidates, and each one names a concrete bug class in this repo. The expected one is the complexity composite: quote() in src/pricing/fare.rs is deeply branched, had two recent bug fixes (airport fee charged twice; promo stacked on capped surge), and its unit tests cover only two paths. Zero candidates, with that reasoning stated, also passes.

FAIL if it proposes three or more candidates, or any candidate rests on a hypothetical bug class.
