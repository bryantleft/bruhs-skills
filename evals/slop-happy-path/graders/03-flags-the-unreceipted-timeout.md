---
type: llm
focus: trace
weight: 1
---

PASS if the report flags `AbortSignal.timeout(10000)` in src/components/Form.tsx as an operational number with no receipt (no measurement, SLA or requirement behind it) and asks for the evidence needed to set it, without proposing a different specific value.

FAIL if it does not mention the timeout, or "fixes" it by suggesting another number (5000, 15000, 30s, ...) as the answer.
