---
type: llm
focus: trace
weight: 1
---

PASS if external dependencies (zustand, zod, @acme/api-client, immer, nanoid, and optionally vitest) appear in a separate frame labeled "External" (or similar) placed to the right of the packages/store frame, not inside it. Collapsing zustand's subpaths into one zustand node is fine.

FAIL if external packages are drawn inside the module frame, are missing, or there is no separate external frame.
