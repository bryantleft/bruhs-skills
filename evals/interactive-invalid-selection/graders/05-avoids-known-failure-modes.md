---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats "foo" as a feature description and starts cook (exploring the code, planning a "foo" feature)
- Claims commands/foo.md exists or describes what it contains
- Responds with only an error, without the list of valid commands
