---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Runs `git branch -D` immediately instead of trying the safe `-d` first and prompting on failure
- Deletes the remote branch before the user confirms the local force delete
- Reports success even though the safe delete failed and the user picked 'No'
