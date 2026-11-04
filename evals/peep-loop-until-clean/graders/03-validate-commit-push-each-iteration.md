---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: after applying an iteration's fixes it runs the full check suite (npm test and the other package.json checks), then commits with a message like `fix: self-review pass (peep loop iteration 1)` and pushes to feat/retry-api-calls, before reviewing again.

FAIL if it does not, if it pushes code whose checks fail, or if the run never reached the step this describes. A push that succeeds but reports it could not write upstream tracking config is an environment quirk, not a failure.
