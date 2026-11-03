---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 8 opens the PR with a `## UI preview` section containing: a 'Verified with /expect (chrome-devtools)' line, the screenshots embedded via hosted URLs (e.g. raw.githubusercontent on the bruhs-assets branch), and the recording (linked, with a note that an inline player needs a manual drag-drop)

FAIL if it does not, or if the run never reached the step this describes.
