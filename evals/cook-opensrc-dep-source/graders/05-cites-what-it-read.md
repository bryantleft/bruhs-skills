---
type: llm
focus: trace
weight: 1
---

PASS if, when explaining the API it coded against, the run cites the file and symbol it read (for example node_modules/react-day-picker/dist/index.js addToRange for the nights semantics, or dist/index.d.ts PropsRange.max).

FAIL if it asserts how DayPicker's props behave with no file or symbol behind the claim.
