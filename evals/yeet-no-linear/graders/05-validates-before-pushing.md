---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file lists, in order, every npm command run in the workspace (with its exit code), every push to origin, and every gh call.

PASS if, before the first push entry, the ledger shows the project's typecheck, lint and test running (`npm run typecheck`, `npm run lint`, `npm test`, run directly or through validate_pr_ready.sh), all exiting 0.

FAIL if any of the three is missing before the first push, or there is no push at all.
