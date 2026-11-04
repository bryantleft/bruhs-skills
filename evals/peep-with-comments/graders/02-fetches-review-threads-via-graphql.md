---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it fetches the PR's review threads with the `gh api graphql` reviewThreads query (getting isResolved, path, line and comment author/body) and reports 4 unresolved threads: lib/db/queries.ts:45, two on components/game/leaderboard-card.tsx, and lib/hooks/use-leaderboard.ts:12.

FAIL if it does not, or if the run never reached the step this describes.
