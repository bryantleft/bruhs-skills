---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Persists the newly discovered stripe-best-practices skill back into the bruhs:state block by piping the updated state JSON into sync_bruhs_block.py --kind state AND re-deriving the rules block (in case Stripe-related rules are added later)

FAIL if it does not, or if the run never reached the step this describes.
