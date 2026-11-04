---
type: llm
focus: trace
weight: 1
---

PASS if Step 7 ends with 'Ready to ship! Run /bruhs:yeet to create ticket and PR.' and no 'Using existing ticket' line, since cook was started from a description rather than a ticket ID.

FAIL if it prints 'Using existing ticket', names a PERDIX ticket as if one exists, or never reaches Step 7.
