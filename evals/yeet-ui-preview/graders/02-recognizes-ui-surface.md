---
type: llm
focus: trace
weight: 1
---

PASS if the run recognizes the diff as user-visible UI (it touches .tsx and .css files: the leaderboard card and the game page) and treats yeet's UI verification and preview step (Step 7.5, practices/ui-preview.md) as applying to this PR.

FAIL if it treats the change as having no UI surface, or never considers the UI preview step.
