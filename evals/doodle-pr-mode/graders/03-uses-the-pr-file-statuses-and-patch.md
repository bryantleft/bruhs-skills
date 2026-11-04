---
type: llm
focus: trace
weight: 1
---

PASS if the run gets the changed files with their statuses from GitHub (`gh api .../pulls/42/files`, ideally with --paginate) and the patch (`gh pr diff 42`), and the diagram reflects those statuses: the three leaderboard/route files and src/db/client.ts as added, src/app/page.tsx and src/db/schema.ts as modified, and src/legacy/top-players.ts as removed.

FAIL if it diagrams from a guess or from local files only, or any of these files has the wrong status in the diagram.
