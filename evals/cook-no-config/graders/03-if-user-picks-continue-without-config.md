---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: If user picks 'Continue without config', skips all Linear-related steps (no ticket lookup, no ticketContext), uses sensible defaults for stack detection, and continues to Step 1 treating the input as a feature description

FAIL if it does not, or if the run never reached the step this describes.
