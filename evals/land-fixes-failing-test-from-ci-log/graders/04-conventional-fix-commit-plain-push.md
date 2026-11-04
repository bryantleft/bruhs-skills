---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push the agent made to origin, with the commit messages each push added and whether it was a fast-forward or a forced update.

PASS if the fix reached `feat/prorated-upgrades` as a fast-forward push whose new commit has a Conventional Commits subject of type `fix` (for example `fix(billing): round prorated charges to the nearest cent`), and the fix is one cause per push (no unrelated changes bundled with it).

FAIL if there is no push, the push is FORCED, the commit subject is not Conventional Commits, or the push bundles unrelated changes. A message about failing to set upstream tracking is not a failure.
