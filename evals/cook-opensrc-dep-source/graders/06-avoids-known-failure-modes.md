---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Codes against a half-remembered react-day-picker API (v8 props, or `max` read as days) without opening the installed source
- Relies solely on web search or docs and never reads the installed copy in node_modules
- Runs `opensrc` against latest instead of the version in the lockfile
- Installs, upgrades, or re-fetches react-day-picker instead of reading what is installed
- Asserts an API shape with no source or file citation behind it
