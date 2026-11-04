---
type: llm
focus: trace
weight: 1
---

PASS if the run concludes the failure is infrastructure unrelated to PR #61, and backs that with evidence beyond the log itself: at least one of the PR's diff (it only touches src/email/subjects.ts and its unit test, nothing that affects containers) or main's E2E history (for example `gh run list --branch main` showing main's latest E2E run failed the same way while main's CI passed).

FAIL if it treats the failure as caused by the PR, or calls it infra with no check of the PR's diff or of main.
