---
type: llm
focus: trace
weight: 1
---

PASS if the run takes the Linear team and project the user already named in the prompt (team Perdix, key PERDIX; project Core), matching them to the ids that linear_get_teams and linear_list_projects returned, and does not stop to ask the user for them again.

FAIL if it ends the run asking which team or project to use, picks a different team or project, or invents ids that the Linear calls did not return.
