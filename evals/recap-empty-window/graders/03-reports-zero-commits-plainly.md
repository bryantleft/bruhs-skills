---
type: llm
focus: trace
weight: 1
---

PASS if the recap says plainly that there are no commits by the user in the window (for example `Recap — <date> → <date>  (0 commits)` and a line saying nothing shipped), without inventing bullets. Mentioning that the only activity was a merge of Alice Chen's branch, or offering a wider window, is fine.

FAIL if the recap produces work bullets for yesterday, or hedges instead of saying there were no commits.
