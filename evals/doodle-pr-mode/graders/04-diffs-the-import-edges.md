---
type: llm
focus: trace
weight: 1
---

PASS if the run compares imports before and after (for example `git show` of the base version of src/app/page.tsx against the branch version) and the diagram shows at least page.tsx -> leaderboard/Leaderboard as an added edge and page.tsx -> legacy/top-players as a removed edge. Drawing preserved edges (such as page.tsx -> components/Header) is optional.

FAIL if it only draws the new import graph, or renders every edge the same way with no added/removed distinction.
