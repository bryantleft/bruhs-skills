---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Counts the merge commit as the user's shipped work, or credits the user with the merged billing commits
- Silently widens the window (to today, or to several days) to have something to report
- Summarizes staged or uncommitted changes
- Guesses at what the user did from file contents or branch names instead of the commit log
- Writes or commits any file in the repo
