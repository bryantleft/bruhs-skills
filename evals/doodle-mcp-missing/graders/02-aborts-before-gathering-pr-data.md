---
type: llm
focus: trace
weight: 1
---

PASS if, after finding no renderer, the run stops without gathering PR data: no `gh pr view`, `gh api .../pulls/...`, `gh pr diff`, `git diff` or rg import scans for the diagram. Reading bruhs's own command docs or the project's CLAUDE.md is fine.

FAIL if it runs any of that PR data-gathering before or after discovering the renderer is missing.
