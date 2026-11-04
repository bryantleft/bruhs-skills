---
type: llm
focus: last_message
weight: 1
---

PASS if the final message reports the PR (URL https://github.com/perdixlabs/game-api/pull/42 or #42), says Linear was not configured so this ran in git-only mode (in substance "⚠ Linear not configured (git-only mode)"), and reminds the user that `/bruhs:claim` enables the Linear integration.

FAIL if it omits the git-only warning or the /bruhs:claim reminder, or reports a ticket.
