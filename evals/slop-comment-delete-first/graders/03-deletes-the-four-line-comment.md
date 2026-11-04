---
type: llm
focus: trace
weight: 1
---

PASS if scripts/deploy.ts ends the run without the four-line comment: deleted outright, or replaced by a single line that names the constraint (the prompt reads the account alias from the session). Recommending deletion and applying it are both expected; a pass needs the file changed or a clear recommendation to delete.

FAIL if the comment is reworded into two or more lines, moved somewhere else, or left as it was without recommending deletion.
