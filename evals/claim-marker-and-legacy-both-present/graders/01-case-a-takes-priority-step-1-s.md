---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Case A takes priority: Step 1's first probe (read_bruhs_block.py --kind state) finds a marker block, so claim immediately enters the Reconfigure prompt (Yes / No) — NOT the migration prompt (Case B)

FAIL if it does not, or if the run never reached the step this describes.
