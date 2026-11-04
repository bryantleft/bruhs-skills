---
type: llm
focus: trace
weight: 1
---

PASS if the recap has 2 to 5 bullets, with the CSV export feat and its comma-quoting fix (both SHOP-230) combined into one bullet, and the "style: format export module", "chore: fix lint", "chore: fix lint again" and "fix: typo in export button label" commits dropped or rolled into a single bullet.

FAIL if each commit gets its own bullet, the SHOP-230 work is split, or the noise commits are padded out into separate accomplishments.
