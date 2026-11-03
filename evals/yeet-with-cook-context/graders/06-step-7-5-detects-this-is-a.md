---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 7.5 detects this is a UI change (a settings-page toggle), verifies it with `/expect` (chrome-devtools), and captures screenshots (desktop + mobile, ideally light/dark) plus a short screen recording of toggling dark mode, per practices/ui-preview.md

FAIL if it does not, or if the run never reached the step this describes.
