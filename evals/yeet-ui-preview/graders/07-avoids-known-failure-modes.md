---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Skips Step 7.5 silently and opens the UI PR as if no preview were needed
- Embeds a bare `<screenshot>` placeholder, or images or a recording that were never captured
- Claims the UI was verified with /expect, or that a recording plays inline from a CLI upload
- References a local /tmp path in the PR body instead of saying nothing was captured
- Tries to install packages to get a browser working, then reports that as done when the install failed
- Writes a non-Conventional commit message or PR title
