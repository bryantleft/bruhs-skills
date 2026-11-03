---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Overwrites the bruhs:state block in CLAUDE.md and AGENTS.md without asking, losing custom fields the user added by hand
- Exits immediately on detecting the file without offering the reconfigure option
- Merges the new detection into the existing config in a destructive way (e.g. wiping stack.libraries)
