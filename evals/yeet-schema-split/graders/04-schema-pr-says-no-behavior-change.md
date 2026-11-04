---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every `gh pr create` and `gh pr edit` with the full title and body.

PASS if the schema PR's body says, in substance, that it carries no behavior change on its own (it only adds the reward_grants table, which nothing reads or writes until the next PR), and says the code that uses it follows in a stacked PR (by number, branch, or "next in the stack").

FAIL if there is no schema PR, or its body describes reward-granting behavior as if this PR ships it, or doesn't say that it changes no behavior.
