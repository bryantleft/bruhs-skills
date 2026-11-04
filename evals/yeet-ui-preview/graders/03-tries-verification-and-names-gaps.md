---
type: llm
focus: trace
weight: 1
---

PASS if the run tries the documented verification path before giving up on it, for example looking for the /expect skill or chrome-devtools tools, checking for an installed Playwright, or trying `npm run dev`, and then states specifically what is missing (no /expect or chrome-devtools in this session, dependencies such as next and playwright not installed, so no dev server or browser).

FAIL if it skips verification without checking anything, or claims to have verified the UI in a browser.
