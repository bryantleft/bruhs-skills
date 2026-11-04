---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin with the full message of each new commit.

PASS if every commit on the three pushed branches has a Conventional Commits subject (`feat(scope): ...` or similar), and every commit has an `Assisted-by: <Agent>:<model-id>` trailer naming a model. The original WIP commits ("wip: rewards", "wip ui", "fix schema + tests") must not appear in any pushed branch.

FAIL if any pushed commit has a non-conventional subject, lacks the Assisted-by trailer, or a WIP commit was pushed.
