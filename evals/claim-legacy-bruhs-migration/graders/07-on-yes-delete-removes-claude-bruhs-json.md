---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: On 'Yes, delete': removes .claude/bruhs.json (and rmdir .claude only if empty). On 'No, keep both': leaves the legacy file alone (it will be ignored by read_bruhs_block.py since the marker block now exists)

FAIL if it does not, or if the run never reached the step this describes.
