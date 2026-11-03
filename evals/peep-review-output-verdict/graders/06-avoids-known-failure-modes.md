---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Posts a Block against a commit that is no longer head
- Reports a finding without a validation note
- Surfaces a generic rebase nit
