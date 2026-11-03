---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Because the leaderboard is a UI change, the Visual Verification step runs `/expect` (Skill('expect')) against the running dev server to verify rendering/sorting/empty-state/mobile via chrome-devtools, then captures screenshots + a recording to /tmp/bruhs-ui-preview per practices/ui-preview.md — it does NOT use the stale Skill('agent-browser')

FAIL if it does not, or if the run never reached the step this describes.
