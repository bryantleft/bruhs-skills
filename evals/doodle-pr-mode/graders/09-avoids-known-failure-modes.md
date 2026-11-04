---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Skips the old-vs-new import diff and renders every file as modified with no distinct added/removed edges
- Claims the diagram was posted when gh gist create or gh pr comment was never run
- Commits the image into the repo or pushes, which the user did not ask for
