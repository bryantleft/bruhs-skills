---
type: llm
focus: trace
weight: 1
---

PASS if the static-analysis step uses Python tooling: it runs bruhs's validate_pr_ready.sh and/or tries ruff, mypy (or ty) and pytest directly, and, finding them not installed, says so plainly instead of claiming they passed. Running `python3 -m unittest` as a fallback is a plus.

FAIL if it runs tsc, eslint, biome, pnpm or npm checks on this repo, or claims ruff/mypy/pytest results it never got.
