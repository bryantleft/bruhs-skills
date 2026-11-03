---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Silently treats 'foo' as a feature description and runs cook
- Hallucinates a commands/foo.md file and tries to Read it
- Fails loudly with a stack-trace-style error instead of offering the valid subcommand list
