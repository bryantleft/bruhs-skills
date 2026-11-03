---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Calls out the legacy .claude/bruhs.json in the prompt or in a one-line note BEFORE the user picks Yes/No: 'A legacy .claude/bruhs.json is also present and will be ignored by read_bruhs_block.py — clean it up if you no longer need it.'

FAIL if it does not, or if the run never reached the step this describes.
