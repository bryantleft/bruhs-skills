---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it asks for the migration files (the SQL, the journal entry and the schema change) to move into their own PR that merges before the code PR.

FAIL if it does not, or if the run never reached the step this describes.
