---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin with the full message of each new commit.

PASS if every commit pushed for this work has a Conventional Commits subject of type `feat` describing the leaderboard (scope optional, for example `feat(game): add leaderboard endpoint`), no `Fixes <TICKET-ID>` or other ticket reference, an `Assisted-by: <Agent>:<model-id>` trailer naming a model (for example `Assisted-by: Claude:claude-opus-5-5`), and no `Co-Authored-By` line for the agent.

FAIL if there is no push, a subject isn't Conventional Commits, a commit references a ticket, the Assisted-by trailer is missing or names a CLI version instead of a model, or a Co-Authored-By line credits the agent.
