---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Assumes WIP means the user wants yeet and skips the menu
- Runs git stash or git add -A before asking the user
- Offers slop in the menu
- Claims the changes were committed, stashed or ticketed when they were not
