---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 1 detects the existing bruhs:state block in CLAUDE.md via the read_bruhs_block.py probe (with legacy .claude/bruhs.json fallback)

FAIL if it does not, or if the run never reached the step this describes.
