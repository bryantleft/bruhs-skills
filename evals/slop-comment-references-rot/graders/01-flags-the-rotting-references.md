---
type: llm
focus: trace
weight: 1
---

PASS if the run flags the comments added on this branch that cite things that rot: the plan ID ('covers R4 from the plan'), the person/channel ('per Sam in #backend'), the line number ('see ledger.ts line 88'), and the date ('temporary, remove after 2027-02'), and says that provenance like this belongs in the commit message or PR body. At least three of the four, plus the commit/PR-body point, is a pass. Noticing that ledger.ts has no line 88 is a plus, not required.

FAIL if it flags fewer than three of them, or flags them without saying where the provenance should go instead.
