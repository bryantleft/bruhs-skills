---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it checks for bruhs stashes (`git stash list | grep "bruhs:"` or equivalent), finds none, and does not ask about restoring a stash.

FAIL if it does not, or if the run never reached the step this describes.
