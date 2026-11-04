---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: no naming, formatting or plain magic-number suggestion (for example about the bare 86_400_000 or the variable `d` in memberSinceDays) appears among the findings shown to the user, and the run reports how many lint-territory suggestions it filtered (a `[debug] filtered N lint-territory suggestions` line or a count in the summary, 0 included).

FAIL if it does not, or if the run never reached the step this describes.
