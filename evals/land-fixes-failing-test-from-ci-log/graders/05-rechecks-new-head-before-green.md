---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file lists, in order, every push and every `gh pr checks` call with the commit it reported on and each check's result.

PASS if, after the push of the fix, the agent calls `gh pr checks` again (polling or `--watch`) on the new head commit until a call reports every check (typecheck, lint, test, Vercel) as pass.

FAIL if no `gh pr checks` call after the fix push reports all checks passing on the new head, for example if it stopped after seeing them pending.
