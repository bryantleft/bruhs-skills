---
type: llm
focus: mock_calls
weight: 1
---

These are the Linear tool calls the agent made.

PASS if there is no call to `linear_create_issue` and no call to `linear_edit_issue`. Read-only calls (get_teams, get_user, get_issue, search) are fine.

FAIL if it created or edited a Linear issue.
