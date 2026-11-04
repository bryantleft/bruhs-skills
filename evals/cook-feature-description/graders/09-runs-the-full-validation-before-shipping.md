---
type: llm
focus: trace
weight: 1
---

PASS if, before reporting ready to ship, the run runs the project's full checks (`npm run typecheck`, `npm run lint` and `npm test`, directly or through validate_pr_ready.sh) and they pass, or it stops and reports a failure.

FAIL if it reports ready to ship without running all three, or while one of them fails.
