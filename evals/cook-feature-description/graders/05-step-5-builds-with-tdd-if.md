---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5 builds with TDD if a test suite is detected (vitest.config.* check), keeps tests when suite exists, otherwise creates then deletes temp test files

FAIL if it does not, or if the run never reached the step this describes.
