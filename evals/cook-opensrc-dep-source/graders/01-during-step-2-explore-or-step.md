---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: During Step 2 (Explore) or Step 5 (Build), the agent resolves react-day-picker's real API from source rather than memory — reads the installed copy in node_modules at the locked v9, or runs `opensrc path react-day-picker` and greps/reads its exports/types — per practices/source-ground-truth.md

FAIL if it does not, or if the run never reached the step this describes.
