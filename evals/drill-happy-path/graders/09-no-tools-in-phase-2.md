---
type: llm
focus: trace
weight: 1
---

PASS if Phase 2 stays tool-agnostic: it does not recommend specific runners or libraries (Stryker, Cypress, Playwright, dependency-cruiser, eslint-plugin-boundaries, diff-cover, ...) as the adoption.

FAIL if a candidate's proposed adoption names a specific tool to install.
