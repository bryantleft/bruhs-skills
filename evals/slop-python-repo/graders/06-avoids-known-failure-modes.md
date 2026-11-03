---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Loads typescript-react.md practices by default and reports React-specific anti-patterns in Python code
- Treats the per-request client construction as a style issue instead of a P3 performance bug (the command doc explicitly says these are bugs, not optimizations)
- Runs `pnpm tsc --noEmit` and `pnpm lint` in the verification step on a Python repo
