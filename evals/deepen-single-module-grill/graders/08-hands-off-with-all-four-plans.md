---
type: llm
focus: trace
weight: 1
---

PASS if the hand-off includes all four: an implementation plan /bruhs:cook can pick up; a test plan at the new module's interface (what is tested in-process, against PGlite, and with a fake deposit adapter); a migration plan for src/api/reservations.ts, src/admin/reservations.ts and src/jobs/reminders.ts; and a tests-to-delete list naming the existing tests that become waste (for example ReservationManager.test.ts's argument pass-through test and the copied validation tests in src/api and src/admin).

FAIL if any of the four is missing.
