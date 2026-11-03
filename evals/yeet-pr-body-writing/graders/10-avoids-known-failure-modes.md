---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Narrates the diff ('the handler reads X then calls Y')
- Packs the three cases into one comma/semicolon sentence
- Writes the body in lowercase chat style
- Lists verification steps under Risks, or writes 'No risks'
