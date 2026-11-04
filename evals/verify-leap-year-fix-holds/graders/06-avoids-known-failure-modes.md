---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Returns VERIFIED from running the test suite on HEAD alone, with no run against the pre-fix code
- Invents a numeric pass threshold (a percentage, a count of passing cases) that nothing in the repo or the request supplies
- Edits src/dates.ts (verify proves a claim; it does not change the code under test)
- Softens the verdict ("mostly verified", "verified with caveats") or gives two verdicts
- Asks the user to restate the claim and stops, when the claim names the file and behavior specifically enough to test
