---
type: llm
focus: trace
weight: 1
---

PASS if the final answer's verdict is VERIFIED and it follows the command's output shape: the verdict line, a `Claim:` line with the falsifiable claim, an `Evidence:` section giving baseline and treatment values (e.g. baseline=RangeError, treatment={ year: 2000, ... }), a `Reasoning:` paragraph, and an `Artifacts:` line (inline is fine).

FAIL if the verdict is NOT VERIFIED or INCONCLUSIVE, if there is more than one verdict, or if the Evidence section lacks either the baseline or the treatment value.
