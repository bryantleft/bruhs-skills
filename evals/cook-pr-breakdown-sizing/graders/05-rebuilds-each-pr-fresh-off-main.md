---
type: llm
focus: trace
weight: 1
---

PASS if the plan says that after the spike, each PR is rebuilt fresh off main and the spike branch is thrown away, rather than carving the spike branch into the PR stack.

FAIL if it plans to split, cherry-pick, or carve the spike branch into PRs, or doesn't say what happens to the spike.
