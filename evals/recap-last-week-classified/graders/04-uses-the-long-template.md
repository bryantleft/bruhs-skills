---
type: llm
focus: trace
weight: 1
---

PASS if the output follows the long template for a 5-day-or-longer window: a `Recap — <from> → <to>` header with commit, file and +/- LOC counts, bullets tagged with their ticket IDs where the commits carry one ([SHOP-210], [SHOP-214], [SHOP-219], and "(no ticket)" or no tag for the rest), and a `Classification:` paragraph after the bullets.

FAIL if the header counts are missing, ticket IDs present in the commit bodies are dropped, or there is no Classification paragraph.
