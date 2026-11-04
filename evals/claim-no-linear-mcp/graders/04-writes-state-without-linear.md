---
type: llm
focus: trace
weight: 1
---

PASS if the run writes a bruhs:state block (sync_bruhs_block.py or equivalent) to both CLAUDE.md and AGENTS.md whose integrations object has no "linear" key at all, and whose tooling.mcps does not list linear.

FAIL if nothing is written, either file lacks the block, integrations.linear is present with null / empty / placeholder values, or tooling.mcps includes "linear".
