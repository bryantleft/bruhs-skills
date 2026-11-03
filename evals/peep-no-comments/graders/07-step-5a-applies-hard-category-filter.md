---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5a applies hard category filter — drops `suggestion`-severity issues whose normalized summary matches lint-territory keywords (naming, formatting, import order, magic number without coupling concern, etc.) and logs the dropped count as a debug line

FAIL if it does not, or if the run never reached the step this describes.
