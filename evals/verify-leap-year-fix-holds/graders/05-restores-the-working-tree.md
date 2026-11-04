---
type: llm
focus: trace
weight: 1
---

PASS if, by the end of the run, the repo is back where it started: on branch fix/leap-year-400 (not a detached HEAD or main), with src/dates.ts at the fix version, no stash left behind from the verification, and any temporary harness either in /tmp or removed from the repo. Judge from the agent's own commands (switch back, stash pop, cleanup) and any git status it shows.

FAIL if the run ends on a detached HEAD or another branch, leaves a verification stash, or leaves repro files committed or untracked in the repo without saying so.
