---
type: llm
focus: trace
weight: 1
---

PASS if, before rewording anything, the run asks whether the comment above `await ensureSession();` in scripts/deploy.ts needs to exist at all (for example by deleting it and rereading the two calls, or by checking what a reader would get wrong without it).

FAIL if it goes straight to shortening or rephrasing the comment without considering deletion.
