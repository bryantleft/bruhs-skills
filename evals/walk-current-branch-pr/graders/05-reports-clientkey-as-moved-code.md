---
type: llm
focus: trace
weight: 1
---

PASS if the walkthrough reports clientKey() as moved verbatim from src/server.ts to src/lib/clientKey.ts (in the Moved code section or an equivalent note), so the reviewer knows src/lib/clientKey.ts is not new logic.

FAIL if src/lib/clientKey.ts is presented as new behavior, or the move is not mentioned.
