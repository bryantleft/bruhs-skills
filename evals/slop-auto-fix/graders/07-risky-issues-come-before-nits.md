---
type: llm
focus: trace
weight: 1
---

PASS if, when the run presents what is left after the auto-fixes, the type-signature issues (`any`) and the security issues (hardcoded secrets) come first, ahead of any lower-priority findings such as naming, style or architecture nits.

FAIL if lower-priority findings are presented or asked about before the `any` types and secrets.
