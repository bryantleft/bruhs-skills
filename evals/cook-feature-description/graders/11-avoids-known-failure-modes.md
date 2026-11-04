---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Tries to fetch a Linear ticket for a plain-English feature description
- Invents multiple cosmetic variants just to hit an approach count
- Gives the leaderboard a size, page length, cache or timeout number with no receipt, instead of reusing STATS_PAGE_SIZE (the top-10 product spec in src/lib/stats.ts) or citing another receipt
- Fetches each agent's name with a separate await inside a loop, copying the N+1 in src/app/stats/page.tsx, instead of one join or batched query
- Invokes a non-existent Skill('agent-browser') for visual verification
- Marks the UI feature done by eyeballing it, or claims screenshots or a recording that were never captured
- Ends with 'Using existing ticket' text even though cook was not started from a ticket ID
