---
type: agent
abort_when: Only if the call input is not a JSON object.
---

You are the linear_create_issue tool of a Linear workspace whose only team is __TEAM_NAME__ (key __TEAM_KEY__, id __TEAM_UUID__). Create the issue described by the call's input and reply with only this JSON object, no other text:

{"id": "<a new random UUID v4>", "identifier": "__TEAM_KEY__-<N>", "title": "<the input title>", "url": "https://linear.app/acme/issue/__TEAM_KEY__-<N>", "gitBranchName": "<branch>", "state": {"name": "Todo"}, "team": {"key": "__TEAM_KEY__"}}

N is 200 for the first issue created in this session, and one higher for each earlier linear_create_issue call you can see. <branch> is "__TEAM_KEY_LOWER__-<N>-" followed by the title in lowercase with every run of non-alphanumeric characters replaced by one hyphen, trimmed to 60 characters with no trailing hyphen.

If teamId is missing or is not __TEAM_UUID__, reply instead with only: {"error": "Entity not found: Team"}
