---
type: llm
focus: last_message
weight: 1
---

PASS if the final summary says the existing ticket was reused (in substance "Using existing ticket: PERDIX-145 Add dark mode toggle to settings page"), names the branch and the PR (https://github.com/perdixlabs/settings-app/pull/45 or #45), says PERDIX-145 moved to In Review, and mentions that the UI preview (browser verification, screenshots, recording) is still to do.

FAIL if it reports a new ticket, omits PERDIX-145, or presents the PR as complete without mentioning the missing preview.
