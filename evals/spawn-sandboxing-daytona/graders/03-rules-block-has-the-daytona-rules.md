---
type: llm
focus: trace
weight: 1
---

PASS if the bruhs:rules block the run writes is produced by derive_stack_rules.py from the state JSON and contains the "Daytona (sandboxing)" section: run AI-generated or untrusted code inside a Daytona sandbox, reuse one sandbox rather than one per call, delete sandboxes and set an idle auto-stop, pass secrets via the sandbox env, and bound concurrency.

FAIL if no rules block is written, it lacks the Daytona section, or the run hand-writes rules instead of deriving them.
