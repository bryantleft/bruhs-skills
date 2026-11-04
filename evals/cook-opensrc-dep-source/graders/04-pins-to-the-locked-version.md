---
type: llm
focus: trace
weight: 1
---

PASS if the run works against the version in package-lock.json and node_modules (react-day-picker 9.4.4), and where its memory or docs disagree with that source, it says so and follows the installed source. It does not fetch or reason about `latest`.

FAIL if it fetches or describes a different version (latest, v8) as the one it coded against, or changes the dependency version.
