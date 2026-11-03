---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Skips Phase 3b and presents only one alternative — fails the 'design it twice' rule
- Recommends per-PR mutation testing without confronting the 10-minute CI budget
- Ignores the CI budget constraint entirely
- Picks a specific tool (Mutmut) in 3a before any alternatives are designed
- Writes the actual pyproject.toml mutation config and CI step instead of staying in plan form
- Drafts an ADR auto-rejecting mutation testing without grilling the user for a load-bearing reason
