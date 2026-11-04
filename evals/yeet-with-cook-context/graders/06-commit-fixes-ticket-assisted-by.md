---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin with the full message of each new commit.

PASS if the pushed commit has a `feat` Conventional Commits subject, a body line `Fixes PERDIX-145` (the ticket in the body, not the subject), an `Assisted-by: <Agent>:<model-id>` trailer naming a model (for example `Assisted-by: Claude:claude-opus-5-5`), and no `Co-Authored-By` line for the agent.

FAIL if `Fixes PERDIX-145` is missing, the ticket is in the subject, the Assisted-by trailer is missing or names a CLI version instead of a model, or a Co-Authored-By line credits the agent.
