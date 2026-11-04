---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` (and any `gh pr edit`) with the full PR body. The repo's PR template has exactly two headings, `## Summary` then `## Test plan`, plus two checkboxes.

PASS if the final PR body keeps those two headings, in that order, with no heading added, renamed or removed. yeet's own parts (decisions, review focus, Linear, testing lines, risks) appear as bold lead-in labels inside those sections, not as new `##` headings.

FAIL if no PR was created, or the body adds headings such as `## Linear`, `## Testing`, `## Risks` or `## What changed`, renames a template heading, or drops one.
