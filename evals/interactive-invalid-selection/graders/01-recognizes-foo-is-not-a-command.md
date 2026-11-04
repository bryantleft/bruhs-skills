---
type: llm
focus: trace
weight: 1
---

PASS if the run recognizes that "foo" is not a bruhs command (SKILL.md's index has no foo, and there is no commands/foo.md) and says so to the user. Checking whether commands/foo.md exists, by listing commands/ or a failed read, is fine.

FAIL if it treats "foo" as a command and invents a workflow for it, or never tells the user that foo isn't a command.
