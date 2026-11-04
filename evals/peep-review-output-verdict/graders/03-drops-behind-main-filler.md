---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: no finding shown to the user says the branch is behind main or should be rebased. If a pass raises it, the run drops it as filler because no specific conflict or base-side fix depends on it.

FAIL if a behind-main or rebase item reaches the user's findings, or if the run never reached the step this describes.
