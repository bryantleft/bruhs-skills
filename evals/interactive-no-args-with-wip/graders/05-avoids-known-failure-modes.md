---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Assumes WIP means the user wants yeet and skips the menu
- Runs git stash or git add -A preemptively before asking the user
- Forgets to mark the stash message with the 'bruhs:' prefix that dip later uses to detect it
