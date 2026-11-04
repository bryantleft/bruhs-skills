---
type: llm
focus: trace
weight: 1
---

PASS if the written bruhs:state block carries over the legacy .claude/bruhs.json values unchanged: mcpServer linear-sonner, team 2e557b80-0000-4000-8000-000000000000, project 2e557b80-0000-4000-a000-000000000001, the "refactor": "Polish" label, stack.state "zustand", and tooling.skills [superpowers, shadcn]. Piping the legacy JSON into sync_bruhs_block.py --kind state is the expected way.

FAIL if any of those values is dropped or changed (for example stack.state removed because zustand isn't in package.json, or labels reset to the defaults).
