---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Creates a duplicate Linear ticket via linear_create_issue instead of reusing ticketContext from cook
- Uses a model-invented branch name instead of Linear's gitBranchName slug
- Writes the ticket reference into the commit title (`feat(PERDIX-145): ...`) instead of the commit body
- Skips the full-suite validation gate before pushing — per the workflow, yeet should have confidence the branch compiles/tests before opening a PR
- Opens the PR for this UI change with no UI preview (or a `<screenshot>` placeholder), skipping Step 7.5 /expect verification and screenshot/recording capture
- Captures a screenshot without first verifying the toggle with /expect — a preview of an unverified UI
