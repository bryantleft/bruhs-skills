---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file lists, in order, every push and every `gh pr checks` call with the commit it reported on and each check's result.

PASS if, after the push that fixed cache.ts, a `gh pr checks` call (polling or `--watch`) reports typecheck, lint and test all passing on the new head commit.

FAIL if no `gh pr checks` call after the fix push reports every check passing, for example if it stopped while they were still pending.
