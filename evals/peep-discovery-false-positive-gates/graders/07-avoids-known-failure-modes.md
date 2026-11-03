---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Asks the author a question the Risks section already answers
- Forwards a finding citing a file that doesn't exist
- Treats the green raw-insert repro as proof of a production bug
- Drops the authorization finding because the same file already has the pattern
