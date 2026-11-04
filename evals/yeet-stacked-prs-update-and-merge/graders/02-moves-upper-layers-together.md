---
type: llm
focus: trace
weight: 1
---

PASS if the run moves feat/b-logic and feat/c-ui together rather than leaving one on a stale parent: `git rebase --update-refs` run from feat/c-ui (the top), or an explicit rebase of feat/c-ui onto the rebuilt feat/b-logic after feat/b-logic is rebased.

FAIL if it rebases feat/b-logic but leaves feat/c-ui on the old feat/b-logic, or rebuilds the branches by cherry-picking in a way that drops or duplicates commits.
