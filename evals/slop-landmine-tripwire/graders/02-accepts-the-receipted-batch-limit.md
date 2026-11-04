---
type: llm
focus: trace
weight: 1
---

PASS if the report does not demand a receipt for MAX_IDS_PER_REQUEST = 100: its comment cites docs/upstream-profile-api.md, which states the 100-id limit. Saying it is receipted, or not mentioning it, both pass.

FAIL if the report lists MAX_IDS_PER_REQUEST as an unreceipted magic number.
