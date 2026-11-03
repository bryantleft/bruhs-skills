---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Never offers a Sandboxing / Daytona option despite the project being about running untrusted code
- Selects Daytona but omits the "sandboxing" key from the stack JSON, so derive_stack_rules.py can't pick it up
- Daytona selected but no Daytona rules appear in the bruhs:rules block (signal not iterated in collect_signals)
- Invents a sandboxing provider that isn't an offered option
