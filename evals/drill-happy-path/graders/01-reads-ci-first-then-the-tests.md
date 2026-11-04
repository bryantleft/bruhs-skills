---
type: llm
focus: trace
weight: 1
---

PASS if the run reads .github/workflows/ci.yml as the ground truth for what is enforced, plus the test config (apps/web/vitest.config.ts, apps/web/eslint.config.mjs), and then walks the tests (src/**/*.test.ts and tests/).

FAIL if it never reads the CI workflow, or judges the layers from package.json scripts alone.
