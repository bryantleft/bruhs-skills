---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Creates an empty Linear ticket or opens an empty PR despite no diff
- Runs `git commit --allow-empty` to force a Conventional Commits commit even though nothing changed
- Switches to a new branch before checking for changes, leaving the user on a stray branch
- Treats ignored files (dist/, .env) as changes to ship, or force-adds them
