---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: before addressing threads it presents a summary that orders must-fix before suggestions before the question, separates confirmed findings (reproduced / tooling-confirmed) from anything "unconfirmed — reasoning only", and shows each finding's evidence (✓ reproduced, ⚙ fix-validated, n/a, etc.).

FAIL if it does not, or if the run never reached the step this describes.
