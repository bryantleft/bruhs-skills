---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Asks the author a question the Risks section already answers
- Forwards a finding that cites a file that doesn't exist
- Treats a green raw-insert repro as proof of a production double-post
- Drops or softens the bulk authorization finding because the exports handler has the same gap
- Applies a fix, commits, pushes or posts to the PR although the user asked to keep it local
