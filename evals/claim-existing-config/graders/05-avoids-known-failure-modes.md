---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Overwrites the bruhs:state block in CLAUDE.md or AGENTS.md without asking, which would drop the hand-added stack.libraries (zod, effect) and the custom "refactor": "Tech Debt" label
- Exits on finding the block without offering to reconfigure
- Quietly merges newly detected stack values (e.g. Convex) into the block without asking
- Says the config was updated when nothing was written
