---
type: llm
focus: trace
weight: 1
---

PASS if the recap draws only on jordan@example.com's non-merge commits from 2 to 7 days ago: none of Alice Chen's work (invoice PDF export, token refresh fix) appears, nor the user's own SHOP-190 support-impersonation commit from 12 days ago or the SHOP-225 saved-searches commit from today.

FAIL if any of those four commits shows up in the bullets, the counts, or the classification.
