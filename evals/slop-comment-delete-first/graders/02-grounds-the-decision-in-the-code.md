---
type: llm
focus: trace
weight: 1
---

PASS if the run justifies its decision from what is already in the repo: the call names and order say "session first", and/or getSession() in scripts/session.ts throws a clear error if confirmEnvironment() runs first, and/or the commit "fix: create the session before the environment prompt" already records the reason.

FAIL if it gives no reason grounded in the code or history, or claims the comment is needed without checking any of these.
