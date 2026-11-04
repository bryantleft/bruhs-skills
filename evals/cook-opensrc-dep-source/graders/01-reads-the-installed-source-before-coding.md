---
type: llm
focus: trace
weight: 1
---

PASS if, before writing the DayPicker code, the run reads react-day-picker's installed source: node_modules/react-day-picker/package.json and its dist/index.d.ts or dist/index.js (or tries `opensrc path react-day-picker` first and, when it isn't available offline, falls back to the installed copy), per practices/source-ground-truth.md.

FAIL if it writes the picker without opening any file under node_modules/react-day-picker/, or relies only on memory or docs.
