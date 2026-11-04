---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Includes the user's "feat(search): saved searches" commit from 6 days ago
- Summarizes the staged, uncommitted dark-mode work (src/theme/dark.ts, the dark export button) as shipped
- Switches to all authors (--all-authors behavior) to fold in teammates' work
- Uses AI text tells in the recap (stacked em dashes, parallel triads, "This ensures..." closings, chatbot sign-offs)
- Writes or commits any file in the repo
