---
type: llm
focus: trace
weight: 1
---

PASS if, after writing the state, the run re-derives the rules block by piping the same state JSON through `derive_stack_rules.py` into `sync_bruhs_block.py --kind rules`.

FAIL if it updates the state block and leaves the rules block unrefreshed.
