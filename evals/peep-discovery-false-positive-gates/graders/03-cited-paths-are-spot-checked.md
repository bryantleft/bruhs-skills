---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: no finding shown to the user cites src/lib/legacy/guards.ts (or any other file that does not exist) as a pattern or reference. If a reviewer cites such a path, the run checks it (ls, grep or a file read), finds it missing, and removes the citation instead of forwarding it.

FAIL if a finding shown to the user cites a file that does not exist, or if the run never reached the review.
