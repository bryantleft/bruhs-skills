---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Approves or says Ship because the diff is small or the migration is only an index
- Files the bundling as a suggestion, nitpick or non-blocking note
- Labels the bundling finding unverified or "reasoning only" even though the file list is tool output
- Posts a review or comment to the PR although the user asked to keep everything local
