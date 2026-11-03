---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: After verification, it captures screenshots at desktop 1280x800 and mobile 390x844 AND records a short screen recording of the changed interaction (e.g. the leaderboard updating), via chrome-devtools MCP or the project's Playwright (recordVideo + page.screenshot) as a fallback, saved under /tmp/bruhs-ui-preview, following practices/ui-preview.md

FAIL if it does not, or if the run never reached the step this describes.
