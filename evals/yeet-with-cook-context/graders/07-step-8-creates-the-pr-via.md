---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 8 creates the PR via `gh pr create` using the Feature template (Why / What changed / Design decisions / UI preview / Linear / Test plan), with the `## UI preview` section populated from Step 7.5 (a verified-with-/expect note + screenshots + recording) and 'Linear: PERDIX-145' filled in

FAIL if it does not, or if the run never reached the step this describes.
