---
type: llm
focus: trace
weight: 1
---

PASS if the Risk callouts name the changed guard in src/projects/requireOwner.ts (from `!project || ...` to `project && ...`): a missing or soft-deleted project no longer throws Forbidden. The callout should point at src/projects/requireOwner.ts; a line reference (the guard is at line 10) is welcome but not required, and so is tracing the consequence through saveProject.

FAIL if no risk callout identifies that requireOwner stops rejecting missing or deleted projects.
