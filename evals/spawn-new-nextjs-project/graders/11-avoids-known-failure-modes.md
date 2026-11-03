---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Uses npm or yarn instead of pnpm, even though the command doc explicitly says 'Always use pnpm for TypeScript projects'
- Skips the tooling reconciliation step and leaves both eslint-config-next and biome in package.json
- Writes a github-hosted-runner in ci.yml instead of blacksmith-2vcpu-ubuntu-2204
