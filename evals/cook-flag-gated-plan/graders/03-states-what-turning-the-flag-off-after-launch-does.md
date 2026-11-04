---
type: llm
focus: trace
weight: 1
---

PASS if the plan states what happens to already signed-in partner admins and any in-flight state when the flag is turned off after launch, and accounts for src/flags.ts snapshotting flags into the session at login (with 30-day sessions in src/auth/session.ts): either it evaluates this flag per request, or it says plainly that existing sessions keep access until they expire or are refreshed, and how to cut them off.

FAIL if it treats turning the flag off as an instant, complete rollback without addressing sessions that already hold the flag, or never mentions post-launch disable.
