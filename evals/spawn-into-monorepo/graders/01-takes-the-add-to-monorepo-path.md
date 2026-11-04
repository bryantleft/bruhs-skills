---
type: llm
focus: trace
weight: 1
---

PASS if the run detects the monorepo (turbo.json and pnpm-workspace.yaml at the root) and takes the "add to this monorepo" path with New app, as the user asked, rather than creating a new standalone project or asking the Structure (monorepo / single package) question.

FAIL if it treats the request as a new standalone project, asks which structure to use, or creates the app outside the repo.
