---
type: llm
focus: trace
weight: 1
---

PASS if the state JSON the run writes lists tooling.skills as superpowers, shadcn, vercel-react-best-practices, stripe-best-practices, in that order with nothing dropped, and keeps every other field as it was (stack, tooling.mcps, and integrations.linear with mcpServer linear-perdix and team PERDIX).

FAIL if any existing skill is dropped or reordered (for example because it wasn't available in this session, or because superpowers is "a plugin, not a skill"), stripe-best-practices is missing, or the write loses stack or integrations fields.
