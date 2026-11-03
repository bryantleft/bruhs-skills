---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: The working tree is restored exactly: every repro test created is deleted and every trial fix reverted, with `git status --porcelain` clean

FAIL if it does not, or if the run never reached the step this describes.
