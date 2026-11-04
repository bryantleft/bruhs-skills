---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records each `gh pr create` and `gh pr edit` with the full PR body. The repo has no PR template.

PASS if the PR body follows yeet's shape: it opens with what changes after merge and why (users can pick light, dark or system theme on /settings, and the choice persists), lists changes as behavior, has a Linear section naming PERDIX-145, and a testing part with Ran, Mutation-checked and Not tested lines.

FAIL if no PR was created, PERDIX-145 is missing from the body, or the body narrates the diff instead of stating behavior.
