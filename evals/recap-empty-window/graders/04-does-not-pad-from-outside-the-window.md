---
type: llm
focus: trace
weight: 1
---

PASS if no bullet or count draws on work outside the user's own non-merge commits for yesterday: not the "Merge branch 'feat/billing-export'" commit, not Alice Chen's invoice PDF export or page-break fix, not today's "reject avatars over 5 MB" fix, not the avatar upload from 3 days ago, and not the staged src/profile/crop.ts.

FAIL if any of those is presented as something the user shipped yesterday.
