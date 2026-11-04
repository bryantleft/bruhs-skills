---
type: llm
focus: trace
weight: 1
---

PASS if the run saves the design doc in docs/design/ with the same naming as the existing docs/design/2026-03-01-ledger-split.md: a `YYYY-MM-DD-<kebab-case-slug>.md` file name.

FAIL if the doc goes anywhere else (repo root, docs/, a new folder), uses a different naming scheme, or no doc is written.
