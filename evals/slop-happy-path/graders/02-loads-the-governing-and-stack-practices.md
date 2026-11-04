---
type: llm
focus: trace
weight: 1
---

PASS if the run reads bruhs's practices/engineering-principles.md, practices/type-driven-design.md and practices/typescript-react.md (the React practice the nextjs framework selects) before reporting findings. Reading practices/_common.md as well is expected but not required for a pass.

FAIL if it skips engineering-principles.md or typescript-react.md, or loads a practice for another stack (python, rust, hono) instead.
