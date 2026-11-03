---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: On 'Migrate (recommended)': reads the legacy JSON verbatim and pipes it into sync_bruhs_block.py --kind state — does NOT re-run stack detection, does NOT lose the user's existing mcpServer / team / project IDs

FAIL if it does not, or if the run never reached the step this describes.
