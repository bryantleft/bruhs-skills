---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 6 commits with Conventional Commits title 'feat: add leaderboard to game page', NO 'Fixes TICKET-ID' line since there is no ticket, and an 'Assisted-by: <Agent>:<running-model-id>' trailer

FAIL if it does not, or if the run never reached the step this describes.
