---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Codes against a half-remembered react-day-picker API (e.g. v8 props) without opening the installed source, producing a call that doesn't typecheck against v9
- Relies solely on WebSearch / context7 docs and never reads the actual installed source
- Runs `opensrc` against latest instead of the version in the lockfile
- Asserts an API shape with no source/file citation behind it
