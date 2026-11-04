---
type: llm
focus: trace
weight: 1
---

PASS if any local before/after evidence the agent reports (for example the mocked-fetch test failing on the parent and passing on HEAD) is labeled as proving only that the code now reads data.rates, and the answer notes that test/fixtures/rates-v2.json is hand-written, so it says nothing about what the real provider returns. Also PASS if the agent reports no local evidence at all.

FAIL if the mocked test or the fixture is presented as evidence that the live provider works.
