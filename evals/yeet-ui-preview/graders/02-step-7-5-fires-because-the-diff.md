---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 7.5 fires because the diff matches UI surface (.tsx/.css): it runs `/expect` to verify the leaderboard in a real browser via the chrome-devtools MCP (renders, sorts by win rate, empty state, mobile viewport), and fixes + re-verifies if /expect finds breakage before capturing anything

FAIL if it does not, or if the run never reached the step this describes.
