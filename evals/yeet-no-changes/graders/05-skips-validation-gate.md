---
type: llm
focus: trace
weight: 1
---

PASS if the run does not run the pre-ship validation gate (validate_pr_ready.sh, or `npm run typecheck`, `npm run lint`, `npm test`), because with no changes there is nothing to validate.

FAIL if it runs the validation suite before stopping.
