---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats packages/store as a freeform prompt and generates a fake diagram without reading actual files
- Puts external dependencies inside the module frame instead of in a separate 'External' frame
- Attempts to post a PR comment even though the user did not pass --pr-comment and module mode has no PR-comment default
