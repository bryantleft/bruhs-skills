---
type: llm
focus: trace
weight: 1
---

PASS if the recap has 2 to 5 bullets, each one short functional clause, with the three SHOP-210 commits (fuzzy search, ranking by edit distance, ranking-ties test) collapsed into a single fuzzy-search bullet, and the "fix: typo in cart error message" commit either dropped or rolled into another bullet.

FAIL if there are more than 5 bullets, commits are listed one per bullet, or the SHOP-210 work is split across bullets.
